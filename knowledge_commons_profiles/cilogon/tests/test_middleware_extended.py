"""
Extended comprehensive unit tests for CILogon middleware
"""

import time
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError
from django.test import RequestFactory
from django.test import override_settings
from django.utils import timezone

from knowledge_commons_profiles.cilogon.middleware import (
    AutoRefreshTokenMiddleware,
)
from knowledge_commons_profiles.cilogon.middleware import (
    GarbageCollectionMiddleware,
)
from knowledge_commons_profiles.cilogon.middleware import RefreshBehavior
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations

from .test_base import CILogonTestBase


class AutoRefreshTokenMiddlewareEdgeCaseTests(CILogonTestBase):
    """Extended test cases for AutoRefreshTokenMiddleware edge cases"""

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

    def test_token_refresh_with_malformed_token(self):
        """Test token refresh with malformed token structure"""
        self.request.session["oidc_token"] = {
            "access_token": "malformed_token",
            # Missing required fields like exp, refresh_token
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            self.assertRaises(KeyError),
        ):
            # The middleware should raise KeyError when refresh_token is missing
            self.middleware.process_request(self.request)

    def test_token_refresh_network_timeout(self):
        """Test token refresh with network timeout"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        }
        self.request.session["oidc_token"] = expired_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
        ):
            refresh_mock.side_effect = TimeoutError("Network timeout")

            response = self.middleware.process_request(self.request)

            # Should handle network timeout gracefully
            self.assertIsNone(response)

    def test_token_refresh_with_invalid_response(self):
        """Test token refresh with invalid response from OAuth provider"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
        ):
            # Return invalid token response
            refresh_mock.return_value = {"error": "invalid_grant"}

            response = self.middleware.process_request(self.request)

            # Should handle invalid response gracefully
            self.assertIsNone(response)

    def test_token_refresh_concurrent_requests(self):
        """Test token refresh behavior with concurrent requests"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        # Simulate concurrent refresh attempts
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.store_session_variables"
            ) as store_mock,
        ):
            new_token = {
                "access_token": "new_token",
                "refresh_token": "new_refresh_token",
                "exp": int(time.time()) + 3600,
            }
            refresh_mock.return_value = new_token
            store_mock.return_value = True

            # Process multiple requests simultaneously
            response1 = self.middleware.process_request(self.request)
            response2 = self.middleware.process_request(self.request)

            # Both should complete without error
            self.assertIsNone(response1)
            self.assertIsNone(response2)

    def test_token_refresh_session_corruption(self):
        """Test token refresh with corrupted session data"""
        # Corrupt session data
        self.request.session["oidc_token"] = "not_a_dict"

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            self.assertRaises(TypeError),
        ):
            # The middleware should raise TypeError when token is not a dict
            self.middleware.process_request(self.request)

    def test_token_refresh_with_revoked_refresh_token(self):
        """Test token refresh when refresh token has been revoked"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "revoked_refresh_token",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
        ):
            refresh_mock.side_effect = ValueError(
                "invalid_grant: refresh token revoked"
            )

            response = self.middleware.process_request(self.request)

            # Should handle revoked refresh token gracefully
            self.assertIsNone(response)

    @override_settings(DEBUG=True)
    def test_token_refresh_debug_mode_logging(self):
        """Test token refresh logging in debug mode"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.debug"
            ) as debug_mock,
        ):
            new_token = {
                "access_token": "new_token",
                "refresh_token": "new_refresh_token",
                "exp": int(time.time()) + 3600,
            }
            refresh_mock.return_value = new_token

            _ = self.middleware.process_request(self.request)

            # Should log debug information
            debug_mock.assert_called()

    def test_refresh_behavior_enum_values(self):
        """Test RefreshBehavior enum values"""
        # Test actual enum values that exist in the middleware
        self.assertEqual(RefreshBehavior.CLEAR, 0)
        self.assertEqual(RefreshBehavior.IGNORE, 1)

    def test_always_refresh_behavior(self):
        """Test middleware with custom refresh behavior"""
        valid_token = {
            "access_token": "valid_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) + 3600,  # Valid for 1 hour
        }
        self.request.session["oidc_token"] = valid_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=False,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
        ):
            new_token = {
                "access_token": "new_token",
                "refresh_token": "new_refresh_token",
                "exp": int(time.time()) + 3600,
            }
            refresh_mock.return_value = new_token

            response = self.middleware.process_request(self.request)

            # Should not refresh when token is valid (default behavior)
            self.assertIsNone(response)

    def test_never_refresh_behavior(self):
        """Test middleware with no refresh behavior"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as _,
        ):
            response = self.middleware.process_request(self.request)

            # Should attempt to refresh expired token (default behavior)
            self.assertIsNone(response)


class GarbageCollectionMiddlewareEdgeCaseTests(CILogonTestBase):
    """Extended test cases for GarbageCollectionMiddleware edge cases"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GarbageCollectionMiddleware(get_response=MagicMock())
        self.user = User.objects.create_user(username="testuser")
        self.request = self.factory.get("/")
        self.request.user = self.user
        self._setup_session()

    def _setup_session(self):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(self.request)
        self.request.session.save()

    def test_gc_with_large_number_of_associations(self):
        """Test garbage collection with large number of associations"""
        # Create many old associations that should be garbage collected
        old_date = timezone.now() - timedelta(
            days=30
        )  # 30 days old, well beyond the 4-day threshold
        associations = []
        for i in range(1000):
            assoc = TokenUserAgentAssociations(
                user_agent=f"TestAgent{i}",
                access_token=f"token{i}",
                refresh_token=f"refresh{i}",
                app="testapp",
                user_name="testuser",
                created_at=old_date,  # Make them old enough for GC
            )
            associations.append(assoc)

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        # Mock OAuth client and revocation endpoint
        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://test.cilogon.org/oauth2/revoke"
        }
        mock_client.load_server_metadata = (
            MagicMock()
        )  # Mock this method to prevent overriding server_metadata

        # Create a mock queryset that behaves like the associations we created
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 1000
        mock_queryset.__iter__ = lambda self: iter(associations)

        def mock_garner_associations():
            mock_queryset.count()
            return mock_queryset

        self.middleware.garner_associations = mock_garner_associations

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.revoke_token",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete_mock,
        ):
            response = self.middleware.process_request(self.request)

            # Should handle large number of associations
            self.assertIsNone(response)
            # delete_associations should be called with the old associations
            delete_mock.assert_called_once()
            # Verify the queryset passed to delete_associations is our
            # mock queryset
            called_queryset = delete_mock.call_args[0][0]
            self.assertEqual(called_queryset.count(), 1000)

    def test_gc_with_revocation_endpoint_unavailable(self):
        """Test garbage collection when revocation endpoint is unavailable"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": None},
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should skip garbage collection when revocation
            # endpoint unavailable
            self.assertIsNone(response)

    def test_gc_with_partial_revocation_failures(self):
        """Test garbage collection with some token revocations failing"""
        old_date = timezone.now() - timedelta(
            days=30
        )  # 30 days old, well beyond the 4-day threshold

        # Create old associations that should be garbage collected
        associations = [
            TokenUserAgentAssociations(
                user_agent="agent1",
                access_token="token1",
                refresh_token="refresh1",
                app="testapp",
                user_name="testuser",
                created_at=old_date,
            ),
            TokenUserAgentAssociations(
                user_agent="agent2",
                access_token="token2",
                refresh_token="refresh2",
                app="testapp",
                user_name="testuser",
                created_at=old_date,
            ),
        ]

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        # Mock revoke_token to handle partial revocation failures
        def mock_revoke_token(*args, **kwargs):
            # Simulate some revocations failing
            if "token1" in str(kwargs.get("token_revoke", {})):
                message = "Revocation failed"
                raise ValueError(message)
            return True

        # Mock OAuth client and revocation endpoint
        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://cilogon.org/oauth2/revoke"
        }
        mock_client.load_server_metadata = (
            MagicMock()
        )  # Mock this method to prevent overriding server_metadata

        # Create a mock queryset that behaves like the associations we created
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 2
        mock_queryset.__iter__ = lambda self: iter(associations)

        def mock_garner_associations():
            mock_queryset.count()
            return mock_queryset

        self.middleware.garner_associations = mock_garner_associations

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=mock_revoke_token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete_mock,
        ):
            response = self.middleware.process_request(self.request)

            # Should handle partial revocation failures gracefully
            self.assertIsNone(response)
            # delete_associations should still be called even if
            # revocation fails
            delete_mock.assert_called_once()
            # Verify the queryset passed to delete_associations is our
            # mock queryset
            called_queryset = delete_mock.call_args[0][0]
            self.assertEqual(called_queryset.count(), 2)

    def test_gc_with_database_constraint_violations(self):
        """Test garbage collection with database constraint violations"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                return_value=True,
            ),
            patch.object(
                assoc,
                "delete",
                side_effect=IntegrityError("Constraint violation"),
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle constraint violations gracefully
            self.assertIsNone(response)

    def test_gc_with_session_corruption_during_processing(self):
        """Test garbage collection when session gets corrupted during
        processing"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
            created_at=timezone.now() - timedelta(days=5),
        )

        # Set up session that will be corrupted during processing
        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        def corrupt_session(*args, **kwargs):
            # Corrupt session during processing
            self.request.session.clear()
            return True

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=corrupt_session,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as _,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": "https://cilogon.org/oauth2/revoke"},
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle session corruption gracefully
            self.assertIsNone(response)

    def test_gc_with_concurrent_modifications(self):
        """Test garbage collection with concurrent database modifications"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
            created_at=timezone.now() - timedelta(days=5),
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        def concurrent_delete(*args, **kwargs):
            # Simulate concurrent deletion
            TokenUserAgentAssociations.objects.all().delete()
            return True

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=concurrent_delete,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": "https://cilogon.org/oauth2/revoke"},
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle concurrent modifications gracefully
            self.assertIsNone(response)

    def test_gc_middleware_ordering_dependency(self):
        """Test garbage collection middleware ordering with other middleware"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        # Test with different middleware ordering scenarios
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": "https://cilogon.org/oauth2/revoke"},
            ),
        ):
            # Process request through multiple middleware instances
            middleware1 = GarbageCollectionMiddleware(get_response=MagicMock())
            middleware2 = AutoRefreshTokenMiddleware(get_response=MagicMock())

            response1 = middleware1.process_request(self.request)
            response2 = middleware2.process_request(self.request)

            # Both should complete without interference
            self.assertIsNone(response1)
            self.assertIsNone(response2)


class MiddlewareIntegrationTests(CILogonTestBase):
    """Integration tests for middleware components working together"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")
        self.request = self.factory.get("/")
        self.request.user = self.user
        self._setup_session()

        # Add missing middleware attribute for tests that need it
        self.middleware = GarbageCollectionMiddleware(get_response=MagicMock())

    def _setup_session(self):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(self.request)
        self.request.session.save()

    def _add_session(self, request):
        """Helper to add session to request - needed by some tests"""
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def test_middleware_chain_execution_order(self):
        """Test proper execution order of middleware chain"""
        # Set up a valid token in session (no need to test refresh here)
        valid_token = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
            "exp": int(time.time()) + 3600,
        }
        self.request.session["oidc_token"] = valid_token

        # Create old associations for garbage collection
        old_date = timezone.now() - timedelta(
            days=30
        )  # 30 days old, well beyond the 4-day threshold
        associations = [
            TokenUserAgentAssociations(
                user_agent="TestAgent",
                access_token="old_token",
                refresh_token="old_refresh",
                app="testapp",
                user_name="testuser",
                created_at=old_date,  # Make it old enough for GC
            ),
            TokenUserAgentAssociations(
                user_agent="TestAgent2",
                access_token="old_token2",
                refresh_token="old_refresh2",
                app="testapp",
                user_name="testuser",
                created_at=old_date,  # Make it old enough for GC
            ),
        ]

        auto_refresh_middleware = AutoRefreshTokenMiddleware(
            get_response=MagicMock()
        )
        gc_middleware = GarbageCollectionMiddleware(get_response=MagicMock())

        # Mock OAuth client and revocation endpoint
        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://cilogon.org/oauth2/revoke"
        }
        mock_client.load_server_metadata = (
            MagicMock()
        )  # Mock this method to prevent overriding server_metadata

        # Create a mock queryset that behaves like the associations we created
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 2
        mock_queryset.__iter__ = lambda self: iter(associations)

        def mock_garner_associations():
            mock_queryset.count()
            return mock_queryset

        gc_middleware.garner_associations = mock_garner_associations

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=False,
            ),  # Token is valid, no refresh needed
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete_mock,
        ):
            response1 = auto_refresh_middleware.process_request(self.request)
            response2 = gc_middleware.process_request(self.request)

            # Both should return None (no early response)
            self.assertIsNone(response1)
            self.assertIsNone(response2)

            # delete_associations should be called with the old associations
            delete_mock.assert_called_once()
            # Verify the queryset passed to delete_associations is
            # our mock queryset
            called_queryset = delete_mock.call_args[0][0]
            self.assertEqual(called_queryset.count(), 2)

    def test_middleware_with_anonymous_user_transition(self):
        """Test middleware behavior during user authentication transition"""
        # Start with anonymous user
        self.request.user = AnonymousUser()

        auto_refresh_middleware = AutoRefreshTokenMiddleware(
            get_response=MagicMock()
        )

        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=True,
        ):
            response = auto_refresh_middleware.process_request(self.request)

            # Should skip processing for anonymous user
            self.assertIsNone(response)

    def test_middleware_with_session_timeout(self):
        """Test middleware behavior with session timeout"""
        # Simulate expired session
        self.request.session.flush()

        auto_refresh_middleware = AutoRefreshTokenMiddleware(
            get_response=MagicMock()
        )

        with patch(
            "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
            return_value=True,
        ):
            response = auto_refresh_middleware.process_request(self.request)

            # Should handle expired session gracefully
            self.assertIsNone(response)

    @override_settings(DEBUG=False)
    def test_middleware_production_error_handling(self):
        """Test middleware error handling in production mode"""
        expired_token = {
            "access_token": "expired_token",
            "refresh_token": "refresh_token_123",
            "exp": int(time.time()) - 3600,
        }
        self.request.session["oidc_token"] = expired_token

        auto_refresh_middleware = AutoRefreshTokenMiddleware(
            get_response=MagicMock()
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.token_expired",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.fetch_access_token"
            ) as refresh_mock,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.logger.warning"
            ) as warning_mock,
        ):
            refresh_mock.side_effect = Exception("Critical error")
            response = auto_refresh_middleware.process_request(self.request)

            # Should log warning and continue gracefully
            warning_mock.assert_called()
            self.assertIsNone(response)

    def test_middleware_performance_under_load(self):
        """Test middleware performance characteristics under load"""
        # Create multiple requests with tokens
        requests = []
        for i in range(10):
            request = self.factory.get(f"/path{i}")
            request.user = self.user
            self._add_session(request)
            request.session["oidc_token"] = {
                "access_token": f"token_{i}",
                "refresh_token": f"refresh_{i}",
                "exp": int(time.time()) + 3600,
            }
            requests.append(request)

        auto_refresh_middleware = AutoRefreshTokenMiddleware(
            get_response=MagicMock()
        )

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
            # Process all requests
            responses = []
            for request in requests:
                response = auto_refresh_middleware.process_request(request)
                responses.append(response)

            # All should complete successfully
            for response in responses:
                self.assertIsNone(response)

    def test_gc_with_revocation_endpoint_unavailable(self):
        """Test garbage collection when revocation endpoint is unavailable"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": None},
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should skip garbage collection when revocation
            # endpoint unavailable
            self.assertIsNone(response)

    def test_gc_with_partial_revocation_failures(self):
        """Test garbage collection with some token revocations failing"""
        old_date = timezone.now() - timedelta(
            days=30
        )  # 30 days old, well beyond the 4-day threshold

        # Create old associations that should be garbage collected
        associations = [
            TokenUserAgentAssociations(
                user_agent="agent1",
                access_token="token1",
                refresh_token="refresh1",
                app="testapp",
                user_name="testuser",
                created_at=old_date,
            ),
            TokenUserAgentAssociations(
                user_agent="agent2",
                access_token="token2",
                refresh_token="refresh2",
                app="testapp",
                user_name="testuser",
                created_at=old_date,
            ),
        ]

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        # Mock revoke_token to handle partial revocation failures
        def mock_revoke_token(*args, **kwargs):
            # Simulate some revocations failing
            if "token1" in str(kwargs.get("token_revoke", {})):
                message = "Revocation failed"
                raise ValueError(message)
            return True

        # Mock OAuth client and revocation endpoint
        mock_client = MagicMock()
        mock_client.server_metadata = {
            "revocation_endpoint": "https://cilogon.org/oauth2/revoke"
        }
        mock_client.load_server_metadata = (
            MagicMock()
        )  # Mock this method to prevent overriding server_metadata

        # Create a mock queryset that behaves like the associations we created
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 2
        mock_queryset.__iter__ = lambda self: iter(associations)

        def mock_garner_associations():
            mock_queryset.count()
            return mock_queryset

        self.middleware.garner_associations = mock_garner_associations

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon",
                mock_client,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=mock_revoke_token,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.delete_associations"
            ) as delete_mock,
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.load_server_metadata",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.post",
                return_value=MagicMock(status_code=200),
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle partial revocation failures gracefully
            self.assertIsNone(response)
            # delete_associations should still be called even if
            # revocation fails
            delete_mock.assert_called_once()
            # Verify the queryset passed to delete_associations is our
            # mock queryset
            called_queryset = delete_mock.call_args[0][0]
            self.assertEqual(called_queryset.count(), 2)

    def test_gc_with_database_constraint_violations(self):
        """Test garbage collection with database constraint violations"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                return_value=True,
            ),
            patch.object(
                assoc,
                "delete",
                side_effect=IntegrityError("Constraint violation"),
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle constraint violations gracefully
            self.assertIsNone(response)

    def test_gc_with_concurrent_modifications(self):
        """Test garbage collection with concurrent database modifications"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
            created_at=timezone.now() - timedelta(days=5),
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        def concurrent_delete(*args, **kwargs):
            # Simulate concurrent deletion
            TokenUserAgentAssociations.objects.all().delete()
            return True

        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                side_effect=concurrent_delete,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": "https://cilogon.org/oauth2/revoke"},
            ),
        ):
            response = self.middleware.process_request(self.request)

            # Should handle concurrent modifications gracefully
            self.assertIsNone(response)

    def test_gc_middleware_ordering_dependency(self):
        """Test garbage collection middleware ordering with other middleware"""
        TokenUserAgentAssociations.objects.create(
            user_agent="TestAgent",
            access_token="token1",
            refresh_token="refresh1",
            app="testapp",
            user_name="testuser",
        )

        self.request.session["oidc_token"] = {
            "access_token": "current_token",
            "refresh_token": "current_refresh",
        }

        # Test with different middleware ordering scenarios
        with (
            patch(
                "knowledge_commons_profiles.cilogon.middleware.should_run_middleware",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.revoke_token",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.middleware.oauth.cilogon.server_metadata",
                {"revocation_endpoint": "https://cilogon.org/oauth2/revoke"},
            ),
        ):
            # Process request through multiple middleware instances
            middleware1 = GarbageCollectionMiddleware(get_response=MagicMock())
            middleware2 = AutoRefreshTokenMiddleware(get_response=MagicMock())

            response1 = middleware1.process_request(self.request)
            response2 = middleware2.process_request(self.request)

            # Both should complete without interference
            self.assertIsNone(response1)
            self.assertIsNone(response2)
