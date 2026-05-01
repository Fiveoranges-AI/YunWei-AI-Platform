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
    # v1.2: relaxed CSP for legacy agent UIs that ship hand-written HTML
    # with inline <style>/<script>, style="..." attrs, and assorted font
    # URLs. CSP3 quirk: when script-src has BOTH 'nonce-XXX' and
    # 'unsafe-inline', browsers ignore 'unsafe-inline' and require the
    # nonce on every inline tag. Since yinhu's index.html doesn't carry
    # nonces yet, drop nonce + strict-dynamic so 'unsafe-inline' actually
    # takes effect. v1.3 will make agents nonce-aware (X-CSP-Nonce header
    # platform already sends → agent injects into inline tags) and we'll
    # restore the strict nonce-only mode.
    # Note: csp_nonce is still computed and forwarded to agent for v1.3
    # forward-compat; just not advertised in this header.
    del csp_nonce  # silence unused-arg lints; consumed in v1.3
    csp = (
        "default-src 'none'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
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
