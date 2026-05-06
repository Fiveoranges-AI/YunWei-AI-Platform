"""SSO.md §3, §3.2 反向代理核心(SSE 透传 + 断开传播)."""
from __future__ import annotations
import time
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from . import db, hmac_sign
from .response_headers import (
    sanitize_agent_response_headers, inject_security_headers, make_csp_nonce,
)

_HTTP_CLIENT = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=None, write=30, pool=5),
)


async def reverse_proxy(
    request: Request, *, client_id: str, agent_id: str,
    user: dict, subpath: str,
) -> StreamingResponse:
    tenant = db.get_tenant(client_id, agent_id)
    if tenant is None:
        raise HTTPException(404, {"error": "unknown_tenant", "message": "tenant 不存在"})
    if tenant["health"] == "unhealthy":
        raise HTTPException(502, {"error": "agent_unavailable", "message": "agent 暂时不可达"})

    # path 重写 + 保留 query
    qs = request.url.query
    upstream_path = subpath if subpath.startswith("/") else "/" + subpath
    if qs:
        upstream_path += "?" + qs
    upstream_url = tenant["container_url"].rstrip("/") + upstream_path

    body = await request.body()

    # Internal Docker tenants (http://agent-foo:8000) don't care about the
    # forwarded Host header for routing, so we forward the public host so
    # the agent's HMAC verify sees the host the user's browser sent.
    #
    # External HTTPS tenants (e.g. https://gendan.fiveoranges.ai) sit behind
    # a CDN/Vercel/Cloudflare that routes by Host header — forwarding the
    # platform's public Host (app.fiveoranges.ai) makes the upstream router
    # 404 because it's looking for a project bound to that Host.
    # For those we forward the upstream URL's host and sign the HMAC with
    # the same value so the agent verifies cleanly.
    public_host = request.headers.get("host", "")
    upstream_host = httpx.URL(upstream_url).host
    is_external_https = tenant["container_url"].startswith("https://")
    sign_host = upstream_host if is_external_https else public_host

    auth_headers = hmac_sign.sign(
        secret=tenant["hmac_secret_current"], key_id=tenant["hmac_key_id_current"],
        method=request.method, host=sign_host,
        path=upstream_path,
        client=client_id, agent=agent_id,
        user_id=user["id"], user_role="user", user_name=user.get("display_name", ""),
        body=body,
    )
    forward_headers = {**auth_headers}
    for h in ("content-type", "accept", "accept-language", "x-csrf-token"):
        v = request.headers.get(h)
        if v:
            forward_headers[h] = v
    if not is_external_https and public_host:
        forward_headers["host"] = public_host
    # else: leave Host unset; httpx defaults to upstream URL host, which is
    # what we signed and what external CDNs need for routing.
    nonce = make_csp_nonce()
    forward_headers["X-CSP-Nonce"] = nonce

    started = time.time()

    # 关键:build_request + send(stream=True) 不会 auto-close,可以手动管理
    upstream_req = _HTTP_CLIENT.build_request(
        request.method, upstream_url, headers=forward_headers, content=body,
    )
    try:
        upstream_resp = await _HTTP_CLIENT.send(upstream_req, stream=True)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise HTTPException(502, {"error": "agent_unavailable", "message": str(e)})

    async def body_iter():
        try:
            async for chunk in upstream_resp.aiter_raw():
                if await request.is_disconnected():
                    break
                yield chunk
        except httpx.RemoteProtocolError:
            pass
        finally:
            await upstream_resp.aclose()
            duration_ms = int((time.time() - started) * 1000)
            db.write_proxy_log(
                user_id=user["id"], client_id=client_id, agent_id=agent_id,
                method=request.method, path=subpath,
                status=upstream_resp.status_code, duration_ms=duration_ms,
                ip=request.client.host if request.client else None,
            )

    sanitized = sanitize_agent_response_headers(
        list(upstream_resp.headers.raw),
        allowed_set_cookie_prefixes=[f"{client_id}_{agent_id}_"],
    )
    is_app = request.headers.get("host", "").startswith(("app.", "demo.", "api."))
    final = inject_security_headers(sanitized, csp_nonce=nonce, is_app_subdomain=is_app)
    out_headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in final}
    media_type = out_headers.get("content-type")

    return StreamingResponse(
        body_iter(),
        status_code=upstream_resp.status_code,
        headers=out_headers,
        media_type=media_type,
    )
