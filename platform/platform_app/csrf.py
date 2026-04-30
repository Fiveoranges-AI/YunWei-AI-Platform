"""SSO.md §7.2 CSRF double-submit."""
import hmac

def verify_double_submit(header_value: str | None, cookie_value: str | None) -> bool:
    if not header_value or not cookie_value:
        return False
    return hmac.compare_digest(header_value, cookie_value)
