"""
Asynchronous broker views for the standalone IDMS service.

These mirror the *behaviour* of the synchronous broker views in
:mod:`knowledge_commons_profiles.cilogon.views` (``silent_login`` and
``verify_broker_nonce``) but are written as ``async`` views so they can be
served by an ASGI server (uvicorn) in the separate IDMS container. There, a
single worker can hold many concurrent, I/O-bound silent-login redirects
without consuming a thread per request — which is the whole point of splitting
the broker out from the main WSGI/gthread app.

The security-critical crypto/validation has a single source of truth: these
views reuse the existing, unchanged helpers in
:mod:`knowledge_commons_profiles.cilogon.oauth`
(``validate_return_to`` / ``build_broker_redirect``) via ``sync_to_async``,
rather than re-implementing them.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import quote as urlquote

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import build_broker_redirect
from knowledge_commons_profiles.cilogon.oauth import validate_return_to
from knowledge_commons_profiles.cilogon.timing import TimingCollector
from knowledge_commons_profiles.cilogon.timing import apply_header

logger = logging.getLogger(__name__)


def _no_session_url(return_to: str, final_redirect: str) -> str:
    """Build the return_to URL carrying ``no_session=1``.

    Pure string assembly, kept local so the async view's no-session contract
    matches the synchronous ``silent_login`` exactly.
    """
    separator = "&" if "?" in return_to else "?"
    no_session_url = f"{return_to}{separator}no_session=1"
    if final_redirect:
        no_session_url += f"&final_redirect={urlquote(final_redirect, safe='')}"
    return no_session_url


@require_http_methods(["GET"])
async def silent_login(request):
    """
    Silent SSO check for broker apps (async).

    If the user has an active authenticated session, generates a broker
    token and redirects to return_to with it. Otherwise redirects to
    return_to with no_session=1. Does not create or modify session state.
    """
    timings = TimingCollector()
    return_to = request.GET.get("return_to", "")
    final_redirect = request.GET.get("final_redirect", "")

    with timings.span("validate"):
        return_to_ok = bool(return_to) and await sync_to_async(
            validate_return_to
        )(return_to)
    if not return_to_ok:
        # No safe URL to bounce back to: log and send the browser to the
        # configured fallback (e.g. a public homepage) instead of leaving
        # the user staring at a JSON error.
        logger.warning(
            "silent_login: missing or invalid return_to=%r, "
            "redirecting to fallback",
            return_to,
        )
        response = redirect(settings.BROKER_FALLBACK_REDIRECT_URL)
        response["Cache-Control"] = "no-store"
        return response

    user = await request.auser()
    if user.is_authenticated:
        userinfo = await sync_to_async(request.session.get)("oidc_userinfo", {})
        if userinfo and userinfo.get("sub"):
            with timings.span("sub_lookup"):
                sub_association = await (
                    SubAssociation.objects.select_related("profile")
                    .filter(sub=userinfo["sub"])
                    .afirst()
                )
            if sub_association:
                with timings.span("redirect_build"):
                    broker_url = await sync_to_async(build_broker_redirect)(
                        userinfo,
                        return_to,
                        sub_association.profile,
                        final_redirect=final_redirect,
                    )
                if broker_url:
                    response = redirect(broker_url)
                    response["Cache-Control"] = "no-store"
                    apply_header(response, timings)
                    return response

    response = redirect(_no_session_url(return_to, final_redirect))
    response["Cache-Control"] = "no-store"
    apply_header(response, timings)
    return response


@csrf_exempt
@require_http_methods(["POST"])
async def verify_broker_nonce(request):
    """
    Back-channel endpoint for third-party apps to verify and consume a
    one-time broker nonce (async).

    Requires Authorization: Bearer <STATIC_API_BEARER> header.
    Accepts JSON body: {"nonce": "<nonce>"}
    Returns 200 with {"valid": True, "sub": "..."} on success.
    Returns 401 for bad auth, 410 for expired/used/missing nonce.
    """
    timings = TimingCollector()

    # Validate bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JsonResponse({"error": "Missing authorization"}, status=401)

    bearer_token = auth_header[7:]
    if bearer_token != settings.STATIC_API_BEARER:
        return JsonResponse({"error": "Invalid authorization"}, status=401)

    # Parse nonce from body
    try:
        body = json.loads(request.body)
        nonce = body.get("nonce", "")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not nonce:
        return JsonResponse({"error": "Missing nonce"}, status=400)

    # Look up and consume nonce
    cache_key = f"broker_nonce:{nonce}"
    with timings.span("cache_lookup"):
        nonce_data = await cache.aget(cache_key)

    if not nonce_data:
        return JsonResponse({"error": "Nonce expired or not found"}, status=410)

    # Delete nonce immediately to prevent replay
    with timings.span("cache_delete"):
        await cache.adelete(cache_key)

    response = JsonResponse({"valid": True, "sub": nonce_data.get("sub", "")})
    apply_header(response, timings)
    return response


async def broker_health(request):
    """
    Readiness probe for the IDMS container (async).

    Confirms the two backends the broker depends on — the Redis cache and the
    default database — are reachable, so the load balancer / ECS can gate
    traffic on real readiness rather than mere process liveness. The build
    metadata baked into the image is echoed back so the deployed branch, image
    tag and commit SHA are visible on the probe.
    """
    meta = {
        "Branch": settings.APP_BRANCH,
        "Image": settings.BUILD_TAG,
        "SHA": settings.GIT_SHA,
    }
    try:
        await cache.aget("broker_health_probe")
        await SubAssociation.objects.filter(pk=0).aexists()
    except Exception:  # any backend failure here means the broker is unhealthy
        logger.exception("broker health check failed")
        return JsonResponse({"status": "fail", **meta}, status=500)
    return JsonResponse({"status": "ok", **meta})


def broker_404(request, exception=None):
    """
    Minimal 404 handler for the standalone IDMS URLconf.

    IDMS runs under ``config.broker_urls`` without the main app's base
    template or URL names, so the project's normal error pages cannot render
    here (they reverse main-app URLs). Return a small JSON body instead of
    failing to render a template.
    """
    return JsonResponse({"error": "not found"}, status=404)


def broker_500(request):
    """Minimal 500 handler for the standalone IDMS URLconf (see broker_404)."""
    return JsonResponse({"error": "server error"}, status=500)
