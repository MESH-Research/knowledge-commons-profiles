
import re
from time import time
from urllib.parse import urlparse

from basicauth.compat import MiddlewareMixin
from django.conf import settings
from django.http import Http404
from django.urls import Resolver404
from django.urls import resolve

from knowledge_commons_profiles.newprofile.views.members import (
    resolve_network_name,
)

# URL names where RefererNavMiddleware must never write to the session.
# The broker silent-login is hit on every page load by every browser and
# its callers don't want a Postgres UPDATE on every check; verify-nonce
# is a server-to-server back-channel with no user session at all (#591).
_NAV_SKIP_URL_NAMES = frozenset(
    {"broker_silent_login", "broker_verify_nonce"}
)


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


class RefererNavMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.domain_map = getattr(settings, "NAV_NETWORK_DOMAIN_MAP", {})

    def __call__(self, request):
        if self.domain_map and not self._is_skipped_url(request):
            referer = request.headers.get("referer")
            if referer:
                self._process_referer(request, referer)
        return self.get_response(request)

    @staticmethod
    def _is_skipped_url(request):
        try:
            url_name = resolve(request.path_info).url_name
        except Resolver404:
            return False
        return url_name in _NAV_SKIP_URL_NAMES

    def _process_referer(self, request, referer):
        parsed = urlparse(referer)
        referer_host = parsed.hostname
        if not referer_host:
            return

        matched_domain = self._match_domain(referer_host)
        if matched_domain:
            request.session["nav_network_domain"] = matched_domain
            request.session["nav_network_domain_ts"] = time()

    def _match_domain(self, referer_host):
        if referer_host in self.domain_map:
            return self.domain_map[referer_host]
        for key, value in self.domain_map.items():
            if referer_host.endswith(f".{key}"):
                return value
        return None


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
