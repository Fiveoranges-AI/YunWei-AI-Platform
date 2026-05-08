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


from platform_app.daily_report.storage import Subscription


def _sub() -> Subscription:
    return Subscription(
        id="sub-1", tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales", "production", "chat", "customer_news"],
        enabled=True,
    )


@pytest.mark.asyncio
async def test_push_sends_markdown_card_to_userid(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        send = mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(200, json={"processQueryKey": "ok"})
        )
        result = await p.push(
            subscription=_sub(),
            markdown_body="# 销售\n- 昨日成交 ¥1.2M",
            link_url="https://app.fiveoranges.ai/daily-report/abc-123",
            title="银湖经营快报 · 2026-05-06 周三",
        )
    assert result.success is True
    body = send.calls[0].request.read().decode()
    assert "userid_xu" in body
    assert "银湖经营快报" in body
    assert "robot_test" in body  # robotCode in payload


@pytest.mark.asyncio
async def test_push_failure_returns_error(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock() as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(500, json={"code": "err", "message": "bad"})
        )
        result = await p.push(
            subscription=_sub(),
            markdown_body="x", link_url="y", title="z",
        )
    assert result.success is False
    assert "500" in result.error or "bad" in result.error


@pytest.mark.asyncio
async def test_push_truncates_long_body(monkeypatch):
    p = _make_pusher(monkeypatch)
    big = "x" * 6000
    with respx.mock() as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        send = mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(200, json={"processQueryKey": "ok"})
        )
        await p.push(subscription=_sub(), markdown_body=big, link_url="y", title="t")
    body = send.calls[0].request.read().decode()
    assert len(body) < 6500  # truncated payload
    assert "完整版" in body or "dashboard" in body
