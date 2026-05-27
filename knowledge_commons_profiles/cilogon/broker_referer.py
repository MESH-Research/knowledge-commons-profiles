"""
Referer gating for browser-facing broker endpoints.

The broker silent-login endpoint is hit by user browsers via JavaScript
embedded on third-party broker apps (e.g. WordPress sites). Verifying the
Referer header against an allowlist closes off cross-origin embedding from
sites that have no business reaching the SSO broker, on top of the existing
return_to allowlist check.

The server-to-server verify-nonce endpoint is NOT gated here — it carries
its own Authorization: Bearer credential.
"""

from urllib.parse import urlparse

from django.conf import settings


def referer_is_allowed(request) -> bool:
    """Return True if the request's Referer host matches an allowed domain.

    Allowed domains come from settings.BROKER_ALLOWED_REFERER_DOMAINS. A
    referer host matches when it equals an allowed domain or is a subdomain
    of one (so works.hcommons.org matches hcommons.org).
    """
    referer = request.headers.get("referer", "")
    if not referer:
        return False

    try:
        host = urlparse(referer).hostname
    except ValueError:
        return False

    if not host:
        return False

    host = host.lower()
    allowed = getattr(settings, "BROKER_ALLOWED_REFERER_DOMAINS", []) or []
    for raw_domain in allowed:
        domain = raw_domain.lower().strip()
        if not domain:
            continue
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False
