import pytest
import httpx
import respx
from platform_app.response_headers import sanitize_agent_response_headers, STRIPPED


def test_strips_set_cookie_by_default():
    headers = [(b"set-cookie", b"app_session=evil; Path=/"), (b"content-type", b"text/html")]
    out = sanitize_agent_response_headers(headers, allowed_set_cookie_prefixes=[])
    assert (b"set-cookie", b"app_session=evil; Path=/") not in out
    assert (b"content-type", b"text/html") in out


def test_allows_whitelisted_set_cookie():
    headers = [(b"set-cookie", b"yinhu_super-xiaochen_state=v; Path=/")]
    out = sanitize_agent_response_headers(
        headers, allowed_set_cookie_prefixes=["yinhu_super-xiaochen_"],
    )
    assert headers[0] in out


def test_strips_security_headers_from_agent():
    headers = [(b"strict-transport-security", b"max-age=10"),
               (b"x-frame-options", b"SAMEORIGIN")]
    out = sanitize_agent_response_headers(headers, allowed_set_cookie_prefixes=[])
    assert out == []
