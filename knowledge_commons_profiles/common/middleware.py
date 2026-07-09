
import re

from basicauth.compat import MiddlewareMixin
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.urls import Resolver404
from django.urls import resolve

from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.newprofile.views.members import (
    resolve_network_name,
)

# HTTP status used for the maintenance page: 503 tells crawlers/monitors the
# outage is temporary rather than a hard error.
MAINTENANCE_STATUS = 503


def render_maintenance_page(request, status: int = MAINTENANCE_STATUS):
    """Render the admin-editable maintenance page.

    Shared by the login short-circuit and the read-only middleware so the page
    is defined in exactly one place.
    """
    return render(
        request,
        "maintenance.html",
        {"maintenance": MaintenanceMode.get_state()},
        status=status,
    )


def user_bypasses_maintenance(user) -> bool:
    """Whether this user should skip maintenance mode entirely.

    Staff and superusers bypass so they can verify the system and toggle it
    off; the Django admin stays reachable via its own login regardless.
    """
    return bool(
        user is not None
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


def maintenance_block(request):
    """Return a maintenance-page response when this request must be blocked,
    or ``None`` to let it proceed.

    Used by the login views to turn a login attempt into the maintenance page
    while maintenance mode is on (staff excepted).
    """
    if MaintenanceMode.is_active() and not user_bypasses_maintenance(
        getattr(request, "user", None)
    ):
        return render_maintenance_page(request)
    return None


class MaintenanceReadOnlyMiddleware:
    """
    When maintenance mode is on, block writes so the site is read-only.

    Unsafe HTTP methods (POST/PUT/PATCH/DELETE) on user-facing views are
    answered with the maintenance page. Safe (read) methods pass through so
    existing sessions can still browse. Staff/superusers bypass entirely, and a
    small allowlist keeps the Django admin, health check, the broker endpoints
    and the machine-to-machine token endpoints working so dependent apps and
    admins are never broken.
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    # url_names that must keep accepting writes even during maintenance.
    ALLOWLIST_URL_NAMES = frozenset(
        {
            "healthcheck",
            "broker_silent_login",
            "broker_verify_nonce",
            "broker_health",
            "broker_timings_debug",
            "logout",
            "actions_post_view",
            "tokens_put_view",
        }
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_block(request):
            return render_maintenance_page(request)
        return self.get_response(request)

    def _should_block(self, request) -> bool:
        if request.method in self.SAFE_METHODS:
            return False
        if not MaintenanceMode.is_active():
            return False

        if user_bypasses_maintenance(getattr(request, "user", None)):
            # Staff bypass so they can verify the system and toggle it off.
            return False

        try:
            match = resolve(request.path_info)
        except Resolver404:
            # An unknown path attempting a write: block it.
            return True

        # The Django admin keeps working (its own login is independent of
        # CILogon), as do the health check, the broker endpoints and the
        # machine-to-machine token endpoints dependent apps rely on.
        if "admin" in match.namespaces:
            return False
        return match.url_name not in self.ALLOWLIST_URL_NAMES


class RequestMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.thread = settings.THREAD

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        self.process_response(request, response)
        return response

    def process_request(self, request):
        self.thread.request = request

    def process_response(self, request, response):
        if hasattr(self.thread, "request"):
            del self.thread.request
        return response


class NetworkSubdomainMiddleware:
    """
    Detect a network subdomain (e.g. stemedplus.profile.hcommons.org)
    and annotate the request with the network it implies.

    Sets ``request.network`` (the canonical society name, resolved
    through KNOWN_SOCIETY_MAPPINGS with a literal fallback) and
    ``request.network_slug`` (the raw subdomain label). Both are None
    when the host is a base domain, an ignored subdomain (e.g. www), a
    nested subdomain, or unrelated to any configured base domain.

    The network may also arrive as a path prefix on the mirrored
    member mounts (/{network}/members/...); those are detected here
    too, so path-prefixed requests are annotated and gated exactly
    like subdomains.

    NETWORK_DISPLAY_NAMES doubles as the network allowlist: a
    subdomain or path prefix whose resolved network has no
    display-name entry is not a network we serve, and the request is
    rejected with a 404 rather than falling through as a phantom
    network.
    """

    # first path segment followed by /members/ that must never be
    # treated as a network prefix: the canonical members tree itself
    # (a user may be named "members"), the /network/<name>/members/
    # route shape, and asset paths
    PATH_RESERVED = frozenset({"members", "network", "static", "media"})

    _PATH_NETWORK_RE = re.compile(r"^/(?P<slug>[^/]+)/members(?:/|$)")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.network = None
        request.network_slug = None

        slug = self._slug_from_host(request.get_host())
        if not slug:
            slug = self._slug_from_path(request.path_info)

        if slug:
            # resolved with the same mapping the /network/ views use,
            # so subdomain and path-based scoping always agree
            network = resolve_network_name(slug)
            if network.lower() not in settings.NETWORK_DISPLAY_NAMES:
                msg = f"Unknown network: {slug}"
                raise Http404(msg)
            request.network_slug = slug
            request.network = network

        return self.get_response(request)

    @classmethod
    def _slug_from_path(cls, path: str) -> str | None:
        match = cls._PATH_NETWORK_RE.match(path)
        if not match:
            return None
        slug = match.group("slug").lower()
        if slug in cls.PATH_RESERVED:
            return None
        return slug

    @staticmethod
    def _slug_from_host(host: str) -> str | None:
        host = host.partition(":")[0].lower()

        for base in settings.NETWORK_SUBDOMAIN_BASE_DOMAINS:
            base_domain = base.lower()
            if host == base_domain:
                return None
            if host.endswith("." + base_domain):
                slug = host[: -len(base_domain) - 1]
                if (
                    slug
                    and "." not in slug
                    and slug not in settings.NETWORK_SUBDOMAIN_IGNORED
                ):
                    return slug
                return None

        return None
