"""
Tests for HostAwareCookieDomainMiddleware.

The instance answers hosts on more than one registrable domain, so the
session/CSRF cookie domain must be chosen per host: a cookie scoped to
one registrable domain is rejected by the browser on another. Hosts
matching COOKIE_DOMAIN_OVERRIDES get the mapped domain (empty string =
host-only); every other host keeps the global SESSION_COOKIE_DOMAIN.
"""

from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.common.middleware import (
    HostAwareCookieDomainMiddleware,
)

SESSION = "sessionid"
CSRF = "csrftoken"


@override_settings(
    ALLOWED_HOSTS=["*"],
    SESSION_COOKIE_NAME=SESSION,
    CSRF_COOKIE_NAME=CSRF,
    SESSION_COOKIE_DOMAIN=".profile.hcommons.org",
    COOKIE_DOMAIN_OVERRIDES={"stemedplus.org": ""},
)
class HostAwareCookieDomainMiddlewareTests(TestCase):
    def _response_for(self, host, *, set_session=True, set_csrf=True):
        def get_response(request):
            response = HttpResponse()
            if set_session:
                response.set_cookie(
                    SESSION, "s", domain=".profile.hcommons.org"
                )
            if set_csrf:
                response.set_cookie(CSRF, "c", domain=".profile.hcommons.org")
            return response

        request = RequestFactory().get("/", HTTP_HOST=host)
        return HostAwareCookieDomainMiddleware(get_response)(request)

    def test_alias_host_makes_cookies_host_only(self):
        response = self._response_for("profile.stemedplus.org")
        self.assertEqual(response.cookies[SESSION]["domain"], "")
        self.assertEqual(response.cookies[CSRF]["domain"], "")

    def test_alias_host_match_is_case_insensitive(self):
        response = self._response_for("PROFILE.STEMEDPLUS.ORG")
        self.assertEqual(response.cookies[SESSION]["domain"], "")

    def test_apex_of_override_domain_is_host_only(self):
        response = self._response_for("stemedplus.org")
        self.assertEqual(response.cookies[SESSION]["domain"], "")

    def test_other_host_cookies_are_untouched(self):
        response = self._response_for("profile.hcommons.org")
        self.assertEqual(
            response.cookies[SESSION]["domain"], ".profile.hcommons.org"
        )
        self.assertEqual(
            response.cookies[CSRF]["domain"], ".profile.hcommons.org"
        )

    def test_network_subdomain_cookies_are_untouched(self):
        response = self._response_for("stemedplus.profile.hcommons.org")
        self.assertEqual(
            response.cookies[SESSION]["domain"], ".profile.hcommons.org"
        )

    def test_response_without_cookies_is_passed_through(self):
        response = self._response_for(
            "profile.stemedplus.org", set_session=False, set_csrf=False
        )
        self.assertNotIn(SESSION, response.cookies)

    def test_unrelated_domain_is_not_matched_by_suffix(self):
        # "notstemedplus.org" must not match the "stemedplus.org" entry
        response = self._response_for("notstemedplus.org")
        self.assertEqual(
            response.cookies[SESSION]["domain"], ".profile.hcommons.org"
        )


@override_settings(
    ALLOWED_HOSTS=["*"],
    SESSION_COOKIE_NAME=SESSION,
    CSRF_COOKIE_NAME=CSRF,
    SESSION_COOKIE_DOMAIN=".profile.hcommons.org",
    COOKIE_DOMAIN_OVERRIDES={},
)
class HostAwareCookieDomainMiddlewareNoOpTests(TestCase):
    def test_empty_map_leaves_all_cookies_untouched(self):
        def get_response(request):
            response = HttpResponse()
            response.set_cookie(SESSION, "s", domain=".profile.hcommons.org")
            return response

        request = RequestFactory().get(
            "/", HTTP_HOST="profile.stemedplus.org"
        )
        response = HostAwareCookieDomainMiddleware(get_response)(request)
        self.assertEqual(
            response.cookies[SESSION]["domain"], ".profile.hcommons.org"
        )
