"""
Broker-client helpers for satellite Profiles hosts.

A satellite host (its own registrable domain, e.g. profile.stemedplus.org,
listed in ``BROKER_CLIENT_HOSTS``) cannot share the hub session cookie, so
it authenticates as a broker client of the hub (``CILOGON_REGISTERED_DOMAIN``):

* login bounces to the hub's ``/login/`` with a ``return_to`` pointing at the
  local consumer; the hub runs (or reuses) CILogon, which creates the hub
  session, then returns a one-time broker token;
* the local consumer verifies and consumes that token and starts a host-only
  local session;
* anonymous page views silently check the hub via ``/broker/silent-login/`` so
  a login made on any other Commons domain is reflected here too.

Because every login still flows through the hub, the hub session stays the
single SSO source of truth and propagates to all domains.
"""

import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from knowledge_commons_profiles.cilogon.oauth import _broker_encoder


def is_broker_client_host(host: str) -> bool:
    """Return True if ``host`` is a configured broker-client host."""
    host = host.partition(":")[0].lower()
    hosts = getattr(settings, "BROKER_CLIENT_HOSTS", [])
    return host in {h.lower() for h in hosts}


def _hub_base() -> str:
    """Return the https base URL of the profiles hub to delegate to."""
    hub = (
        getattr(settings, "BROKER_CLIENT_HUB", "")
        or settings.CILOGON_REGISTERED_DOMAIN
    )
    return f"https://{hub}"


def consumer_return_to(request) -> str:
    """Return the absolute https URL of this host's broker-token consumer."""
    url = request.build_absolute_uri(reverse("broker_client_login"))
    return url.replace("http://", "https://", 1)


def _hub_url(path: str, request, final_redirect: str) -> str:
    query = {"return_to": consumer_return_to(request)}
    if final_redirect:
        query["final_redirect"] = final_redirect
    return f"{_hub_base()}{path}?{urlencode(query)}"


def hub_login_url(request, final_redirect: str = "") -> str:
    """Build the hub ``/login/`` URL that returns a token to this host."""
    return _hub_url("/login/", request, final_redirect)


def hub_silent_login_url(request, final_redirect: str = "") -> str:
    """Build the hub ``/broker/silent-login/`` URL for an inbound SSO check."""
    return _hub_url("/broker/silent-login/", request, final_redirect)


def consume_broker_token(token: str) -> dict | None:
    """Decode, validate and one-time-consume a broker token.

    Returns the decoded payload on success, or None when the token is
    malformed, expired, or its nonce is missing/already used. The nonce is
    deleted on success so a token cannot be replayed.
    """
    if not token:
        return None

    try:
        payload = _broker_encoder().decode(token)
    except (ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None

    nonce = payload.get("nonce")
    exp = payload.get("exp")
    if not nonce or not exp or time.time() > exp:
        return None

    # One-time use: the nonce must still be present in the shared cache.
    # Delete it first so concurrent replays cannot both succeed.
    cache_key = f"broker_nonce:{nonce}"
    nonce_data = cache.get(cache_key)
    if not nonce_data:
        return None
    cache.delete(cache_key)

    return payload
