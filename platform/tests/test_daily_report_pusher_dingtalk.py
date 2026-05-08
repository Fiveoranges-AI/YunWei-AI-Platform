"""DingTalkPusher tests — all DingTalk HTTP calls mocked via respx."""
import time
import pytest
import httpx
import respx
from platform_app.daily_report.pushers.dingtalk import DingTalkPusher


def _make_pusher(monkeypatch) -> DingTalkPusher:
    monkeypatch.setenv("DINGTALK_CLIENT_ID", "cli_test")
    monkeypatch.setenv("DINGTALK_CLIENT_SECRET", "sec_test")
    monkeypatch.setenv("DINGTALK_AGENT_ID", "agent_test")
    monkeypatch.setenv("DINGTALK_ROBOT_CODE", "robot_test")
    # Reload settings so env changes take effect.
    import importlib, platform_app.settings as s
    importlib.reload(s)
    return DingTalkPusher()


@pytest.mark.asyncio
async def test_access_token_fetched_and_cached(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        token_route = mock.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        ).mock(return_value=httpx.Response(200, json={
            "accessToken": "TOK1", "expireIn": 7200,
        }))
        t1 = await p._get_access_token()
        t2 = await p._get_access_token()  # served from cache
        assert t1 == "TOK1" == t2
        assert token_route.call_count == 1


@pytest.mark.asyncio
async def test_access_token_refetches_after_expiry(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            side_effect=[
                httpx.Response(200, json={"accessToken": "TOK1", "expireIn": 7200}),
                httpx.Response(200, json={"accessToken": "TOK2", "expireIn": 7200}),
            ]
        )
        await p._get_access_token()
        # Force expiry.
        p._token_expires_at = time.time() - 1
        t = await p._get_access_token()
        assert t == "TOK2"
