from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.shortcuts import redirect
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.cilogon.views import RedirectBehaviour
from knowledge_commons_profiles.cilogon.views import app_logout
from knowledge_commons_profiles.cilogon.views import callback
from knowledge_commons_profiles.cilogon.views import cilogon_login

from .test_base import CILogonTestBase


class CILogonViewTests(CILogonTestBase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")
        self.headers = {"HTTP_USER_AGENT": "TestAgent"}

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def test_cilogon_login_redirects_and_flushes(self):
        request = self.factory.get("/auth/login/")
        request.user = AnonymousUser()
        self._add_session(request)

        mock_redirect_response = MagicMock()
        mock_redirect_response.status_code = 302

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.app_logout"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy",
                return_value="abc123",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri",
                return_value="https://example.com/auth/callback",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect",
                return_value=mock_redirect_response,
            ),
        ):
            response = cilogon_login(request)
            self.assertEqual(response, mock_redirect_response)

    def test_callback_forwards_if_forwarding_url_present(self):
        request = self.factory.get("/auth/callback/")
        request.user = self.user
        self._add_session(request)

        response_redirect = redirect("/somewhere")
        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=response_redirect,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.is_request_from_actual_domain",
                return_value=False,
            ),
        ):
            response = callback(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/somewhere")

    @override_settings(
        EXTERNAL_SYNC_CLASSES=[],
    )
    def test_callback_logs_in_user_and_redirects(self):
        request = self.factory.get("/auth/callback/")
        request.user = self.user
        self._add_session(request)

        token = {"access_token": "abc", "refresh_token": "def"}
        userinfo = {"sub": "sub123"}
        mock_assoc = MagicMock()

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token",
                return_value=token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables",
                return_value=userinfo,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.filter"
            ) as sub_filter,
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login"
            ),
        ):
            sub_filter.return_value.first.return_value = mock_assoc
            response = callback(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("my_profile"))

    def test_callback_returns_none_if_no_user_association(self):
        request = self.factory.get("/auth/callback/")
        request.user = self.user
        self._add_session(request)

        token = {"access_token": "abc", "refresh_token": "def"}
        userinfo = {"sub": "nonexistent"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token",
                return_value=token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables",
                return_value=userinfo,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.filter"
            ) as sub_filter,
        ):
            sub_filter.return_value.first.return_value = None

            response = callback(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("associate"))

    def test_app_logout_revokes_tokens_and_redirects(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
            "refresh_token": "R",
        }

        mock_assoc = MagicMock(refresh_token="r", access_token="a")
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter([mock_assoc])

        mock_client = MagicMock()
        mock_client.server_metadata = {"revocation_endpoint": "https://revoke"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter",
                return_value=mock_qs,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client",
                return_value=mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.logout"
            ),
        ):
            response = app_logout(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_app_logout_returns_none_when_no_redirect(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter"
            ) as assoc_mock,
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            assoc_mock.return_value.exists.return_value = False
            response = app_logout(
                request, redirect_behaviour=RedirectBehaviour.NO_REDIRECT
            )
            self.assertIsNone(response)

    def test_app_logout_handles_missing_refresh_token_gracefully(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
        }  # No refresh_token

        mock_assoc = MagicMock(refresh_token="r", access_token="a")
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter([mock_assoc])

        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://revoke",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter",
                return_value=mock_qs,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client",
                return_value=mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ),
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            response = app_logout(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_app_logout_handles_missing_access_token_gracefully(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "refresh_token": "R",
        }  # No access_token

        mock_assoc = MagicMock(refresh_token="r", access_token="a")
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter([mock_assoc])

        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://revoke",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter",
                return_value=mock_qs,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client",
                return_value=mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ),
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            response = app_logout(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_app_logout_skips_revoke_if_no_associations_exist(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
            "refresh_token": "R",
        }

        mock_qs = MagicMock()
        mock_qs.exists.return_value = False

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter",
                return_value=mock_qs,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token"
            ),
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            response = app_logout(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_app_logout_completes_despite_revoke_token_exception(self):
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
            "refresh_token": "R",
        }

        mock_assoc = MagicMock(refresh_token="r", access_token="a")
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter([mock_assoc])

        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://revoke",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter",
                return_value=mock_qs,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client",
                return_value=mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=ValueError("revocation failed"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ),
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            response = app_logout(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/")

    def test_callback_handles_store_session_variables_exception(self):
        request = self.factory.get("/auth/callback/")
        request.user = self.user
        self._add_session(request)

        token = {"access_token": "abc", "refresh_token": "def"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token",
                return_value=token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables",
                side_effect=RuntimeError("store failed"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sentry_sdk.capture_exception"
            ),
            self.assertRaises(RuntimeError),
        ):
            callback(request)

    def test_callback_handles_subassociation_query_failure(self):
        request = self.factory.get("/auth/callback/")
        request.user = self.user
        self._add_session(request)

        token = {"access_token": "abc", "refresh_token": "def"}
        userinfo = {"sub": "some-sub"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token",
                return_value=token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables",
                return_value=userinfo,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.filter",
                side_effect=RuntimeError("db fail"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sentry_sdk.capture_exception"
            ),
            self.assertRaises(RuntimeError),
        ):
            callback(request)
