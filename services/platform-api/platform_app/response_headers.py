"""SSO.md §3.1 响应头净化 + §7.1 安全响应头。"""
from __future__ import annotations
import json
import secrets

# §3.1 必须从 agent 响应剥离的 header(小写比对)
STRIPPED = {
    "set-cookie", "strict-transport-security", "content-security-policy",
    "x-frame-options", "x-content-type-options", "referrer-policy",
    "permissions-policy", "cross-origin-opener-policy", "cross-origin-resource-policy",
    "server", "x-powered-by",
    # hop-by-hop
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    # CORS 应由平台 api 统一管理
    "access-control-allow-origin", "access-control-allow-credentials",
    "access-control-allow-methods", "access-control-allow-headers",
    "access-control-expose-headers", "access-control-max-age",
}


def sanitize_agent_response_headers(
    agent_headers: list[tuple[bytes, bytes]],
    *, allowed_set_cookie_prefixes: list[str],
) -> list[tuple[bytes, bytes]]:
    """剥离危险 header;Set-Cookie 仅放行前缀白名单中的 cookie 名。"""
    out: list[tuple[bytes, bytes]] = []
    for k, v in agent_headers:
        kl = k.decode("latin-1").lower()
        if kl == "set-cookie":
            cookie_name = v.decode("latin-1").split("=", 1)[0].strip()
            if any(cookie_name.startswith(p) for p in allowed_set_cookie_prefixes):
                out.append((k, v))
            continue
        if kl in STRIPPED:
            continue
        out.append((k, v))
    return out


def inject_security_headers(
    headers: list[tuple[bytes, bytes]],
    *, csp_nonce: str, is_app_subdomain: bool,
) -> list[tuple[bytes, bytes]]:
    """SSO.md §7.1 全套响应头。"""
    # v1.3: strict nonce-based CSP for <script> and <style> blocks. Inline
    # tag attributes (style="..." / onclick="...") are allowed via the
    # CSP3 *-src-attr directives without loosening *-src — modern browsers
    # apply *-src-attr to attributes and *-src to <script>/<style> blocks
    # independently.
    #
    # Requires the agent to inject the nonce into its inline tags. Platform
    # forwards the nonce via X-CSP-Nonce header (proxy.py); see yinhu
    # web_agent.py serve_index for the rewrite logic. An agent that
    # doesn't yet support this will have its inline tags blocked — roll
    # back to v1.2 (this file's previous revision) until the agent is
    # nonce-aware.
    csp = (
        "default-src 'none'; "
        f"script-src 'self' 'strict-dynamic' 'nonce-{csp_nonce}'; "
        f"style-src 'self' 'nonce-{csp_nonce}'; "
        "script-src-attr 'unsafe-inline'; "
        "style-src-attr 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: https:; "
        "connect-src 'self'; "
        "worker-src 'self' blob:; "
        "manifest-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "report-uri /csp-report"
    )
    additions = [
        (b"X-Content-Type-Options", b"nosniff"),
        (b"X-Frame-Options", b"DENY"),
        (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
        (b"Permissions-Policy", b"geolocation=(), microphone=(), camera=()"),
        (b"Strict-Transport-Security", b"max-age=31536000; includeSubDomains; preload"),
        (b"Cross-Origin-Opener-Policy", b"same-origin"),
        (b"Cross-Origin-Resource-Policy", b"same-origin"),
        (b"Content-Security-Policy", csp.encode("latin-1")),
    ]
    if is_app_subdomain:
        additions.append((b"X-Robots-Tag", b"noindex, nofollow"))
    return headers + additions


def make_csp_nonce() -> str:
    return secrets.token_urlsafe(16)
