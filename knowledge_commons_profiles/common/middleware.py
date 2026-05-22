
from basicauth.compat import MiddlewareMixin
from django.conf import settings
from django.urls import Resolver404
from django.urls import resolve

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
        from time import time
        from urllib.parse import urlparse

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
