import pytest
from platform_app.firewall import check_request, FirewallReject

HOST = "app.fiveoranges.ai"
DEST = "/yinhu/super-xiaochen/"


def _ok_kwargs(**override):
    base = dict(
        sec_fetch_mode="cors", sec_fetch_site="same-origin",
        referer="https://app.fiveoranges.ai/yinhu/super-xiaochen/",
        host=HOST, dest_path_prefix=DEST,
        csrf_header="abc", csrf_cookie="abc",
        method="POST",  # default to POST so CSRF check is exercised; safe-method tests pass method=GET explicitly
    )
    base.update(override)
    return base


def test_safe_method_skips_csrf():
    # GET / HEAD / OPTIONS pass without CSRF tokens — passive subresources
    # like <img> can't carry them, but cross-site + Referer-prefix checks
    # still protect.
    check_request(**_ok_kwargs(method="GET", csrf_header=None, csrf_cookie=None))
    check_request(**_ok_kwargs(method="HEAD", csrf_header=None, csrf_cookie=None))


def test_navigate_allowed_without_csrf():
    check_request(**_ok_kwargs(sec_fetch_mode="navigate", csrf_header=None, csrf_cookie=None))


def test_cors_with_matching_referer_passes():
    check_request(**_ok_kwargs())


def test_cross_site_blocked():
    with pytest.raises(FirewallReject, match="cross-site"):
        check_request(**_ok_kwargs(sec_fetch_site="cross-site"))


def test_referer_path_mismatch_blocked():
    with pytest.raises(FirewallReject, match="referer path"):
        check_request(**_ok_kwargs(referer="https://app.fiveoranges.ai/other-tenant/agent/"))


def test_referer_host_mismatch_blocked():
    with pytest.raises(FirewallReject, match="host mismatch"):
        check_request(**_ok_kwargs(referer="https://evil.com/yinhu/super-xiaochen/"))


def test_same_origin_post_skips_csrf():
    # Same-origin POST is browser-attested same scheme+host+port; SOP
    # prevents cross-origin attackers from triggering such a request, so
    # CSRF tokens are redundant.
    check_request(**_ok_kwargs(csrf_header=None, csrf_cookie=None))


def test_same_site_missing_csrf_blocked():
    # Same-site (different subdomain like internal.fiveoranges.ai) still
    # needs CSRF — subdomains can't be trusted by SOP alone.
    with pytest.raises(FirewallReject, match="csrf"):
        check_request(**_ok_kwargs(sec_fetch_site="same-site", csrf_header=None))


def test_same_site_csrf_mismatch_blocked():
    with pytest.raises(FirewallReject, match="csrf"):
        check_request(**_ok_kwargs(sec_fetch_site="same-site",
                                    csrf_header="xxx", csrf_cookie="yyy"))


def test_missing_sec_fetch_blocked():
    with pytest.raises(FirewallReject, match="missing Sec"):
        check_request(**_ok_kwargs(sec_fetch_mode=None, sec_fetch_site=None))
