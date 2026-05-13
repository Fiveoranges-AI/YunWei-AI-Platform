"""SSO.md §7.2 跨 agent 防火墙."""
from __future__ import annotations
from urllib.parse import urlparse
from . import csrf as _csrf


class FirewallReject(Exception):
    pass


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def check_request(
    *, sec_fetch_mode: str | None, sec_fetch_site: str | None,
    referer: str | None, host: str,
    dest_path_prefix: str,
    csrf_header: str | None, csrf_cookie: str | None,
    method: str = "GET",
) -> None:
    """Raises FirewallReject on any failure. dest_path_prefix 形如 '/yinhu/super-xiaochen/'."""
    if sec_fetch_mode is None and sec_fetch_site is None:
        # 老浏览器,v1.2 拒绝
        raise FirewallReject("missing Sec-Fetch-* headers")

    if sec_fetch_mode == "navigate":
        return  # 顶级导航放行

    if sec_fetch_site == "cross-site":
        raise FirewallReject("cross-site request blocked")

    # Same-origin / same-site subresource: validate referer prefix.
    if not referer:
        raise FirewallReject("missing Referer for non-navigate")
    parsed = urlparse(referer)
    if parsed.netloc != host:
        raise FirewallReject(f"referer host mismatch: {parsed.netloc} != {host}")
    if not parsed.path.startswith(dest_path_prefix):
        raise FirewallReject(f"referer path {parsed.path} does not start with {dest_path_prefix}")

    # CSRF only required for state-changing methods. Passive subresources
    # (<img>, <link>, fetch GET) can't carry CSRF tokens; the cross-site
    # block + Referer-prefix checks above already prevent cross-agent reads.
    if method.upper() in SAFE_METHODS:
        return

    # Sec-Fetch-Site=same-origin is browser-attested: the request was
    # initiated by JS running on the SAME scheme+host+port. SOP already
    # prevents cross-origin attackers from causing such a request, so the
    # CSRF double-submit check is redundant. Keep the check for same-site
    # (subdomain) and "none" / unknown — those still need defense.
    if sec_fetch_site == "same-origin":
        return

    if not _csrf.verify_double_submit(csrf_header, csrf_cookie):
        raise FirewallReject("csrf failure")
