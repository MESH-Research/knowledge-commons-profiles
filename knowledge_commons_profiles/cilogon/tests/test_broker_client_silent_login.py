"""
Tests for BrokerClientSilentLoginMiddleware.

On a broker-client host an anonymous top-level navigation is redirected
once to the hub's silent-login so a session established on any other
Commons domain is reflected here. The redirect is suppressed for the
hub, authenticated users, non-GET or non-navigation requests, the auth
endpoints, and once the marker cookie is present.
"""

from http import HTTPStatus

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.middleware import (
    BrokerClientSilentLoginMiddleware,
)

CLIENT_HOST = "profile.stemedplus.org"
HUB_HOST = "profile.hcommons.org"
SENTINEL = "OK-PASSED-THROUGH"


@override_settings(
    ALLOWED_HOSTS=["*"],
    BROKER_CLIENT_HOSTS=[CLIENT_HOST],
    BROKER_CLIENT_HUB=HUB_HOST,
    CILOGON_REGISTERED_DOMAIN=HUB_HOST,
    BROKER_CLIENT_SSO_COOKIE="kc_sso_checked",
)
class BrokerClientSilentLoginMiddlewareTests(TestCase):
    def _run(  # noqa: PLR0913
        self,
        host=CLIENT_HOST,
        path="/",
        *,
        user=None,
        cookies=None,
        headers=None,
        method="get",
    ):
        factory = RequestFactory()
        default_headers = {"Accept": "text/html"}
        if headers:
            default_headers.update(headers)
        hdr_kwargs = {
            f"HTTP_{k.upper().replace('-', '_')}": v
            for k, v in default_headers.items()
        }
        request = getattr(factory, method)(
            path, HTTP_HOST=host, **hdr_kwargs
        )
        request.user = user if user is not None else AnonymousUser()
        request.COOKIES = cookies or {}
        mw = BrokerClientSilentLoginMiddleware(
            lambda r: HttpResponse(SENTINEL)
        )
        return mw(request)

    def _passed_through(self, response):
        return response.status_code == HTTPStatus.OK and (
            response.content == SENTINEL.encode()
        )

    def test_anonymous_navigation_redirects_to_hub_silent_login(self):
        response = self._run(path="/members/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith(
                f"https://{HUB_HOST}/broker/silent-login/"
            )
        )
        self.assertIn(
            "final_redirect=https%3A%2F%2Fprofile.stemedplus.org%2Fmembers%2F",
            response["Location"],
        )

    def test_hub_host_is_untouched(self):
        self.assertTrue(self._passed_through(self._run(host=HUB_HOST)))

    def test_authenticated_user_is_untouched(self):
        user = User(username="alice")
        self.assertTrue(self._passed_through(self._run(user=user)))

    def test_marker_cookie_suppresses_the_redirect(self):
        response = self._run(cookies={"kc_sso_checked": "1"})
        self.assertTrue(self._passed_through(response))

    def test_non_get_is_untouched(self):
        self.assertTrue(self._passed_through(self._run(method="post")))

    def test_htmx_request_is_untouched(self):
        response = self._run(headers={"HX-Request": "true"})
        self.assertTrue(self._passed_through(response))

    def test_non_html_request_is_untouched(self):
        response = self._run(headers={"Accept": "application/json"})
        self.assertTrue(self._passed_through(response))

    def test_sec_fetch_non_navigate_is_untouched(self):
        response = self._run(headers={"Sec-Fetch-Mode": "cors"})
        self.assertTrue(self._passed_through(response))

    def test_consumer_path_does_not_loop(self):
        # the consumer endpoint itself must never trigger a silent-login
        response = self._run(path="/client-login/")
        self.assertTrue(self._passed_through(response))

    def test_login_path_is_untouched(self):
        response = self._run(path="/login/")
        self.assertTrue(self._passed_through(response))
