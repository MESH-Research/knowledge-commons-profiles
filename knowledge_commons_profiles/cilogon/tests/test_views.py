from importlib import import_module
from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.shortcuts import redirect
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.cilogon.views import FlushLogoutBehaviour
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

    def test_cilogon_login_passes_prompt_login_when_enabled(self):
        """When should_prompt_login() is True, prompt=login is forwarded to
        CILogon's authorize_redirect so the IdP re-authenticates (#367)."""
        request = self.factory.get("/auth/login/")
        request.user = AnonymousUser()
        self._add_session(request)

        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy",
                return_value="abc123",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri",
                return_value="https://example.com/auth/callback",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.should_prompt_login",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect",
                return_value=MagicMock(status_code=302),
            ) as mock_authorize,
        ):
            cilogon_login(request)

        self.assertEqual(
            mock_authorize.call_args.kwargs.get("prompt"), "login"
        )

    def test_cilogon_login_omits_prompt_login_when_disabled(self):
        """When should_prompt_login() is False, no prompt parameter is sent."""
        request = self.factory.get("/auth/login/")
        request.user = AnonymousUser()
        self._add_session(request)

        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy",
                return_value="abc123",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri",
                return_value="https://example.com/auth/callback",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.should_prompt_login",
                return_value=False,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect",
                return_value=MagicMock(status_code=302),
            ) as mock_authorize,
        ):
            cilogon_login(request)

        self.assertNotIn("prompt", mock_authorize.call_args.kwargs)

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
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.select_related"
            ) as sub_select_related,
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login"
            ),
        ):
            sr_filter = sub_select_related.return_value.filter
            sr_filter.return_value.first.return_value = mock_assoc
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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token"
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

    @override_settings(
        SESSION_ENGINE="django.contrib.sessions.backends.cached_db",
        SESSION_CACHE_ALIAS="default",
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            },
        },
    )
    def test_app_logout_terminates_session_in_cache_not_just_db(self):
        """
        Universal logout must end the user's other sessions in every
        layer of the configured store, not only the django_session row.

        Regression guard for the cached_db backend: it reads its cache
        copy before the database, so a logout that deletes only the
        django_session row leaves the cached copy behind and the
        "logged-out" user stays authenticated. app_logout must delete
        through the SessionStore so the cache copy is cleared too.
        """
        engine = import_module(settings.SESSION_ENGINE)

        # the user is signed in on another device: a session carrying
        # their _auth_user_id, persisted by cached_db to both the cache
        # and the django_session table
        other_device = engine.SessionStore()
        other_device["_auth_user_id"] = str(self.user.pk)
        other_device.save()
        session_key = other_device.session_key

        # precondition: that session really does authenticate the user
        self.assertEqual(
            engine.SessionStore(session_key).get("_auth_user_id"),
            str(self.user.pk),
        )

        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)

        with (
            patch("knowledge_commons_profiles.cilogon.views.logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ) as create_client,
        ):
            create_client.return_value.server_metadata = {
                "revocation_endpoint": "https://revoke.test"
            }
            app_logout(
                request,
                redirect_behaviour=RedirectBehaviour.NO_REDIRECT,
                flush_behaviour=FlushLogoutBehaviour.NO_FLUSH_LOGOUT,
            )

        # after logout the session must authenticate nobody: a fresh
        # load (cache first, then DB) comes back empty
        self.assertIsNone(
            engine.SessionStore(session_key).get("_auth_user_id"),
        )

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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token"
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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token"
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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token"
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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token",
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

    def test_app_logout_revocations_run_in_parallel_and_survive_failure(self):
        """Each (association x token_type_hint) revocation is submitted as
        its own future. A failure in one must not skip the others, and the
        request still returns 302."""
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
            "refresh_token": "R",
        }

        n_assocs = 3
        mock_assocs = [
            MagicMock(refresh_token=f"r{i}", access_token=f"a{i}")
            for i in range(n_assocs)
        ]
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter(mock_assocs)

        mock_client = MagicMock()
        mock_client.server_metadata = {"revocation_endpoint": "https://revoke"}

        seen_tokens = []

        def fake_revoke(*args, **kwargs):
            token_value = kwargs.get("token_value")
            seen_tokens.append(token_value)
            # First call fails; others must still run.
            if len(seen_tokens) == 1:
                msg = "synthetic"
                raise ValueError(msg)

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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token",
                side_effect=fake_revoke,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ),
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            response = app_logout(request)

        self.assertEqual(response.status_code, 302)
        # n_assocs * 2 hints + 2 hints for the current session token
        expected_calls = (n_assocs + 1) * 2
        self.assertEqual(
            len(seen_tokens),
            expected_calls,
            "every (association x token_type_hint) pair must be revoked "
            f"(expected {expected_calls}, got {len(seen_tokens)})",
        )

    def test_app_logout_deletes_associations_once_per_call(self):
        """N associations must still result in exactly one delete pass."""
        request = self.factory.get("/logout/", **self.headers)
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "A",
            "refresh_token": "R",
        }

        mock_assocs = [
            MagicMock(refresh_token=f"r{i}", access_token=f"a{i}")
            for i in range(5)
        ]
        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__.return_value = iter(mock_assocs)

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
                "knowledge_commons_profiles.cilogon.views.revoke_single_token"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ) as delete_mock,
            patch("knowledge_commons_profiles.cilogon.views.logout"),
        ):
            app_logout(request)

            self.assertEqual(
                delete_mock.call_count,
                1,
                "delete_associations must run once for the whole queryset, "
                "not once per association "
                f"(was called {delete_mock.call_count} times)",
            )

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
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.select_related",
                side_effect=RuntimeError("db fail"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sentry_sdk.capture_exception"
            ),
            self.assertRaises(RuntimeError),
        ):
            callback(request)
