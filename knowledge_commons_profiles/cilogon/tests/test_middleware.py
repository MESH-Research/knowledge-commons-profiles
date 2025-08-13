from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import FieldError
from django.db.utils import DatabaseError
from django.db.utils import OperationalError
from django.test import RequestFactory

from knowledge_commons_profiles.cilogon.middleware import (
    AutoRefreshTokenMiddleware,
)
from knowledge_commons_profiles.cilogon.middleware import (
    GarbageCollectionMiddleware,
)
from knowledge_commons_profiles.cilogon.middleware import RefreshBehavior
from knowledge_commons_profiles.cilogon.middleware import RefreshTokenStatus
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations

from .test_base import CILogonTestBase


class AutoRefreshTokenMiddlewareTest(CILogonTestBase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AutoRefreshTokenMiddleware(get_response=MagicMock())
        self.user = User.objects.create_user(username="testuser")
        self.request = self.factory.get("/")
        self.request.user = self.user
        self._setup_session()

    def _setup_session(self):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(self.request)
        self.request.session.save()

    def test_skips_if_middleware_flag_false(self):
        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=False,
        ):
            response = self.middleware.process_request(self.request)
            self.assertIs(response, RefreshTokenStatus.MIDDLEWARE_SKIPPED)

    def test_skips_if_no_token(self):
        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=True,
        ):
            response = self.middleware.process_request(self.request)
            self.assertIs(response, RefreshTokenStatus.NO_TOKEN)

    def test_skips_if_user_not_authenticated(self):
        self.request.user = AnonymousUser()
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=True,
        ):
            response = self.middleware.process_request(self.request)
            self.assertIs(response, RefreshTokenStatus.NO_USER)

    def test_creates_token_user_agent_association(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        self.request.headers = {"user-agent": "TestAgent"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=False,
            ),
        ):
            self.middleware.process_request(self.request)
            self.assertTrue(
                TokenUserAgentAssociations.objects.filter(
                    user_agent="TestAgent",
                    user_name=self.user.username,
                    access_token="a",
                    refresh_token="r",
                ).exists()
            )

    def test_skips_if_token_not_expired(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        self.request.headers = {"user-agent": "TestAgent"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=False,
            ),
            patch.object(
                self.middleware, "refresh_user_token"
            ) as refresh_mock,
        ):
            self.middleware.process_request(self.request)
            refresh_mock.assert_not_called()

    def test_triggers_refresh_on_expired_token(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        self.request.headers = {"user-agent": "TestAgent"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch.object(
                self.middleware, "refresh_user_token"
            ) as refresh_mock,
        ):
            self.middleware.process_request(self.request)
            refresh_mock.assert_called_once()

    def test_triggers_hard_refresh(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        self.request.session["hard_refresh"] = True
        self.request.headers = {"user-agent": "TestAgent"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch.object(
                self.middleware, "refresh_user_token"
            ) as refresh_mock,
        ):
            self.middleware.process_request(self.request)
            refresh_mock.assert_called_once_with(
                self.request,
                self.request.session["oidc_token"],
                self.user,
                refresh_behavior=RefreshBehavior.CLEAR,
            )

    def test_refresh_user_token_successful(self):
        self.request.session["oidc_token"] = {
            "access_token": "old",
            "refresh_token": "r",
        }
        with (
            patch.object(
                self.middleware, "acquire_refresh_lock", return_value=True
            ),
            patch.object(self.middleware, "release_refresh_lock") as release,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token",
                return_value={"access_token": "new", "refresh_token": "r"},
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.store_session_variables"
            ) as store,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logout"
            ) as logout_mock,
        ):
            self.middleware.refresh_user_token(
                self.request, self.request.session["oidc_token"], self.user
            )
            release.assert_called_once()
            store.assert_called_once()
            logout_mock.assert_not_called()

    def test_refresh_token_missing_logs_out(self):
        self.request.session["oidc_token"] = {"access_token": "old"}
        with (
            patch.object(
                self.middleware, "acquire_refresh_lock", return_value=True
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logout"
            ) as logout_mock,
            patch.object(self.middleware, "release_refresh_lock"),
        ):
            self.middleware.refresh_user_token(
                self.request, self.request.session["oidc_token"], self.user
            )
            logout_mock.assert_called_once()

    def test_refresh_token_missing_access_token_logs_out(self):
        self.request.session["oidc_token"] = {
            "access_token": "old",
            "refresh_token": "r",
        }
        with (
            patch.object(
                self.middleware, "acquire_refresh_lock", return_value=True
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token",
                return_value={},
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logout"
            ) as logout_mock,
            patch.object(self.middleware, "release_refresh_lock"),
        ):
            self.middleware.refresh_user_token(
                self.request, self.request.session["oidc_token"], self.user
            )
            logout_mock.assert_called_once()

    def test_refresh_lock_skipped(self):
        self.request.session["oidc_token"] = {
            "access_token": "old",
            "refresh_token": "r",
        }
        with (
            patch.object(
                self.middleware, "acquire_refresh_lock", return_value=False
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logout"
            ) as logout_mock,
        ):
            self.middleware.refresh_user_token(
                self.request, self.request.session["oidc_token"], self.user
            )
            logout_mock.assert_not_called()

    def test_oauth_error_logs_out(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        with (
            patch.object(
                self.middleware, "acquire_refresh_lock", return_value=True
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token",
                side_effect=Exception("oops"),
            ),
            patch.object(self.middleware, "release_refresh_lock"),
        ):
            self.middleware.refresh_user_token(
                self.request, self.request.session["oidc_token"], self.user
            )


class GarbageCollectionMiddlewareTest(CILogonTestBase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GarbageCollectionMiddleware(get_response=MagicMock())
        self.user = User.objects.create_user(username="gc_user")
        self.request = self.factory.get("/")
        self.request.user = self.user
        self._setup_session()

    def _setup_session(self):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(self.request)
        self.request.session.save()

    def test_skips_if_middleware_flag_false(self):
        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=False,
        ):
            response = self.middleware.process_request(self.request)
            self.assertIs(response, RefreshTokenStatus.MIDDLEWARE_SKIPPED)

    def test_skips_if_no_token_in_session(self):
        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=True,
        ):
            response = self.middleware.process_request(self.request)
            self.assertIs(response, RefreshTokenStatus.NO_TOKEN)

    def test_does_nothing_if_no_associations(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch.object(
                self.middleware, "garner_associations"
            ) as mock_garner,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.info"
            ) as log_info,
        ):
            mock_garner.return_value.count.return_value = 0
            self.middleware.process_request(self.request)
            log_info.assert_called_with(
                "Garbage collection found nothing to clean"
            )

    def test_skips_if_no_revocation_endpoint(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        mock_client = MagicMock()
        mock_client.server_metadata = {}
        mock_associations = MagicMock()
        mock_associations.count.return_value = 2
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch.object(
                self.middleware,
                "garner_associations",
                return_value=mock_associations,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.warning"
            ) as log_warning,
        ):
            self.middleware.process_request(self.request)
            log_warning.assert_called_once()

    def test_revokes_and_deletes_associations(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        mock_assoc1 = MagicMock(
            refresh_token="r1", access_token="a1", user="u1", user_agent="ua1"
        )
        mock_assoc2 = MagicMock(
            refresh_token="r2", access_token="a2", user="u2", user_agent="ua2"
        )
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 2
        mock_queryset.__iter__.return_value = iter([mock_assoc1, mock_assoc2])
        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://example.org/revoke"
        }
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch.object(
                self.middleware,
                "garner_associations",
                return_value=mock_queryset,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.revoke_token"
            ) as revoke,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete,
        ):
            self.middleware.process_request(self.request)
            self.assertEqual(revoke.call_count, 2)
            delete.assert_called_once_with(mock_queryset)

    def test_revoke_token_set_handles_exceptions(self):
        mock_assoc = MagicMock(
            refresh_token="r", access_token="a", user="u", user_agent="ua"
        )
        mock_client = MagicMock()
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.revoke_token",
                side_effect=ValueError,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.warning"
            ) as log_warn,
        ):
            self.middleware.revoke_token_set(
                [mock_assoc],
                mock_client,
                "https://revoke",
                {"access_token": "t"},
            )
            log_warn.assert_called_once()

    def test_garner_associations_handles_field_error(self):
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.TokenUserAgentAssociations.objects.filter",
                side_effect=FieldError,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.sentry_sdk.capture_exception"
            ) as sentry,
        ):
            result = self.middleware.garner_associations()
            self.assertEqual(list(result), [])
            sentry.assert_called_once()

    def test_garner_associations_handles_database_error(self):
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.TokenUserAgentAssociations.objects.filter",
                side_effect=DatabaseError,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.sentry_sdk.capture_exception"
            ) as sentry,
        ):
            result = self.middleware.garner_associations()
            self.assertEqual(list(result), [])
            sentry.assert_called_once()

    def test_garner_associations_handles_operational_error(self):
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.TokenUserAgentAssociations.objects.filter",
                side_effect=OperationalError,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.sentry_sdk.capture_exception"
            ) as sentry,
        ):
            result = self.middleware.garner_associations()
            self.assertEqual(list(result), [])
            sentry.assert_called_once()

    def test_garner_associations_handles_generic_exception(self):
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.TokenUserAgentAssociations.objects.filter",
                side_effect=Exception,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.sentry_sdk.capture_exception"
            ) as sentry,
        ):
            result = self.middleware.garner_associations()
            self.assertEqual(list(result), [])
            sentry.assert_called_once()

    def test_middleware_runs_full_gc_flow(self):
        self.request.session["oidc_token"] = {
            "access_token": "a",
            "refresh_token": "r",
        }
        fake_assoc = MagicMock(
            refresh_token="r1", access_token="a1", user="u", user_agent="ua"
        )
        fake_qs = MagicMock()
        fake_qs.count.return_value = 1
        fake_qs.__iter__.return_value = iter([fake_assoc])

        mock_client = MagicMock()
        mock_client.server_metadata = {"revocation_endpoint": "https://revoke"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch.object(
                self.middleware, "garner_associations", return_value=fake_qs
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.revoke_token"
            ) as revoke_token,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete_associations,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.info"
            ) as log_info,
        ):
            self.middleware.process_request(self.request)
            revoke_token.assert_called_once()
            delete_associations.assert_called_once_with(fake_qs)
            log_info.assert_any_call("Garbage collecting %s tokens", 1)
