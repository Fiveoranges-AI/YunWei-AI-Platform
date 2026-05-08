"""DingTalk corp app pusher. Sends the daily report markdown card to a userid."""
from __future__ import annotations
import time
import httpx
from .base import Pusher, PushResult
from ..storage import Subscription
from ...settings import settings

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
                "appKey": settings.dingtalk_client_id,
                "appSecret": settings.dingtalk_client_secret,
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
        raise NotImplementedError("Implemented in next task")
