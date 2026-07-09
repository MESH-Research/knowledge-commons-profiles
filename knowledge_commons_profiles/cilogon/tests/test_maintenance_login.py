"""
Tests that new logins are blocked (with the maintenance page) while maintenance
mode is on, and that staff bypass so they are never locked out.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.test import RequestFactory

from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.cilogon.tests.test_base import CILogonTestBase
from knowledge_commons_profiles.cilogon.views import callback
from knowledge_commons_profiles.cilogon.views import cilogon_login


def _enable_maintenance():
    obj = MaintenanceMode.load()
    obj.enabled = True
    obj.title = "Login off"
    obj.message = "<p>No logins right now</p>"
    obj.save()


class MaintenanceLoginBlockTests(CILogonTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def _login_request(self, user):
        request = self.factory.get("/login/")
        request.user = user
        self._add_session(request)
        return request

    def test_anonymous_login_shows_maintenance_page(self):
        _enable_maintenance()
        response = cilogon_login(self._login_request(AnonymousUser()))
        self.assertEqual(response.status_code, 503)
        self.assertIn("No logins right now", response.content.decode())

    def test_staff_login_proceeds_to_cilogon(self):
        _enable_maintenance()
        staff = User.objects.create_user(
            "staffy", password="x", is_staff=True
        )
        sentinel = MagicMock()
        sentinel.status_code = 302
        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "get_forwarding_state_for_proxy",
                return_value="state",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "get_oauth_redirect_uri",
                return_value="https://example.com/cb",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "oauth.cilogon.authorize_redirect",
                return_value=sentinel,
            ),
        ):
            response = cilogon_login(self._login_request(staff))
        self.assertIs(response, sentinel)

    def test_login_proceeds_when_not_in_maintenance(self):
        sentinel = MagicMock()
        sentinel.status_code = 302
        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "get_forwarding_state_for_proxy",
                return_value="state",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "get_oauth_redirect_uri",
                return_value="https://example.com/cb",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "oauth.cilogon.authorize_redirect",
                return_value=sentinel,
            ),
        ):
            response = cilogon_login(self._login_request(AnonymousUser()))
        self.assertIs(response, sentinel)

    def test_callback_blocked_in_maintenance(self):
        _enable_maintenance()
        request = self.factory.get("/cilogon/callback/")
        request.user = AnonymousUser()
        self._add_session(request)
        response = callback(request)
        self.assertEqual(response.status_code, 503)
