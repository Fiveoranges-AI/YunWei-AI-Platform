"""DingTalk corp app pusher. Sends the daily report markdown card to a userid."""
from __future__ import annotations
import time
import httpx
from .base import Pusher, PushResult
from ..storage import Subscription
from ... import settings as _settings_mod

_TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
_SEND_URL = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"


class DingTalkPusher(Pusher):
    """One pusher instance per platform process. Token cache is in-memory."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_TOKEN_URL, json={
                "appKey": _settings_mod.settings.dingtalk_client_id,
                "appSecret": _settings_mod.settings.dingtalk_client_secret,
            })
            resp.raise_for_status()
            data = resp.json()
        self._access_token = data["accessToken"]
        # 90% TTL to avoid edge expiry.
        self._token_expires_at = time.time() + data["expireIn"] * 0.9
        return self._access_token

    async def push(
        self, *,
        subscription: Subscription,
        markdown_body: str,
        link_url: str,
        title: str,
    ) -> PushResult:
        token = await self._get_access_token()
        body = self._truncate(markdown_body, link_url)
        payload = {
            "robotCode": _settings_mod.settings.dingtalk_robot_code,
            "userIds": [subscription.push_target],
            "msgKey": "sampleActionCard",
            "msgParam": (
                # actionCard params per DingTalk docs; serialized as JSON-string-of-string-map
                '{"title":' + _json_str(title) + ','
                '"text":' + _json_str(body) + ','
                '"singleTitle":"打开完整版 + 问小陈",'
                '"singleURL":' + _json_str(link_url) + '}'
            ),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _SEND_URL,
                headers={"x-acs-dingtalk-access-token": token},
                json=payload,
            )
        if resp.status_code >= 400:
            return PushResult(success=False, error=f"{resp.status_code}: {resp.text[:200]}")
        return PushResult(success=True, error=None)

    @staticmethod
    def _truncate(body: str, link_url: str) -> str:
        """DingTalk markdown is ~5000 char; keep generous headroom."""
        MAX = 4500
        if len(body) <= MAX:
            return body
        return body[:MAX].rstrip() + f"\n\n（完整版见 dashboard：{link_url} ）"


def _json_str(s: str) -> str:
    """Embed string as JSON literal (with quotes and escapes) inside the msgParam."""
    import json as _json
    return _json.dumps(s, ensure_ascii=False)
