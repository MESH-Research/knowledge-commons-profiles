"""
Minimal URLconf for the standalone IDMS broker service.

Served by the ASGI (uvicorn) IDMS container, which is path-routed ``/broker/*``
on the *same host* as the main profiles app. It exposes ONLY the broker
endpoints — at their existing, unchanged paths and names — plus a health
probe; every other path 404s, keeping the broker's surface area minimal.

The main app's ``config.urls`` is deliberately left untouched, so it continues
to serve these same paths (via the synchronous views) in local development and
as a fallback if the routing rule is ever removed.
"""

from django.conf import settings
from django.urls import path

from knowledge_commons_profiles.cilogon import broker_views

urlpatterns = [
    path(
        "broker/verify-nonce/",
        broker_views.verify_broker_nonce,
        name="broker_verify_nonce",
    ),
    path(
        "broker/silent-login/",
        broker_views.silent_login,
        name="broker_silent_login",
    ),
    path(
        "broker/health/",
        broker_views.broker_health,
        name="broker_health",
    ),
]

if settings.DEBUG:
    # DEBUG-only profiler, mirroring config.urls. The view also enforces the
    # DEBUG gate itself, so it stays inert if accidentally exposed.
    from knowledge_commons_profiles.cilogon import views_debug

    urlpatterns.append(
        path(
            "broker/_timings/",
            views_debug.broker_timings_debug,
            name="broker_timings_debug",
        )
    )

# IDMS runs under this minimal URLconf, so the project's default error pages
# (which render templates that reverse main-app URL names) cannot resolve here.
# Use small JSON error responses instead.
handler404 = "knowledge_commons_profiles.cilogon.broker_views.broker_404"
handler500 = "knowledge_commons_profiles.cilogon.broker_views.broker_500"
