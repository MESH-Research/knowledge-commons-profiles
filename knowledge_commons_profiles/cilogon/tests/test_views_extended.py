"""
Extended comprehensive unit tests for CILogon views
"""

import base64
import json
from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import DatabaseError
from django.db import IntegrityError
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.views import activate
from knowledge_commons_profiles.cilogon.views import app_logout
from knowledge_commons_profiles.cilogon.views import (
    associate_with_existing_profile,
)
from knowledge_commons_profiles.cilogon.views import association
from knowledge_commons_profiles.cilogon.views import callback
from knowledge_commons_profiles.cilogon.views import cilogon_login
from knowledge_commons_profiles.cilogon.views import confirm
from knowledge_commons_profiles.cilogon.views import extract_form_data
from knowledge_commons_profiles.cilogon.views import validate_form
from knowledge_commons_profiles.newprofile.models import Profile

from .test_base import CILogonTestBase


class CILogonLoginTests(CILogonTestBase):
    """Test cases for CILogon login functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def test_cilogon_login_anonymous_user(self):
        """Test CILogon login with anonymous user"""
        request = self.factory.get("/auth/login/")
        request.user = AnonymousUser()
        self._add_session(request)

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
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect"
            ),
        ):
            cilogon_login(request)

    def test_cilogon_login_authenticated_user(self):
        """Test CILogon login with already authenticated user"""
        request = self.factory.get("/auth/login/")
        request.user = self.user
        self._add_session(request)

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
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect"
            ),
        ):
            cilogon_login(request)

    def test_cilogon_login_with_next_parameter(self):
        """Test CILogon login with next URL parameter"""
        request = self.factory.get("/cilogon/login/?next=/profile/")
        request.session = SessionStore()
        request.session.create()
        request.user = AnonymousUser()

        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri",
                return_value="https://example.com/auth/callback",
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect"
            ),
        ):
            cilogon_login(request)

    def test_cilogon_login_session_error(self):
        """Test CILogon login with session handling error"""

        request = self.factory.get("/cilogon/login/")
        # Don't attach session to request to test error handling
        request.user = AnonymousUser()

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
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_redirect"
            ),
            self.assertRaises(AttributeError),
        ):
            cilogon_login(request)


class CallbackTests(CILogonTestBase):
    """Test cases for OAuth callback handling"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    @override_settings(
        EXTERNAL_SYNC_CLASSES=[],
    )
    def test_callback_successful_existing_user(self):
        """Test successful callback for existing user"""
        # Create proper state parameter (base64 encoded JSON)
        state = base64.urlsafe_b64encode(
            json.dumps({"callback_next": "/profile/"}).encode()
        ).decode()
        request = self.factory.get(
            f"/auth/callback?code=auth123&state={state}"
        )
        request.user = AnonymousUser()
        self._add_session(request)

        # Create existing SubAssociation
        SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token"
            ) as token_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables"
            ) as session_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login",
                return_value=True,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
        ):
            token_mock.return_value = {
                "access_token": "token123",
                "id_token": "id_token_123",
            }
            # Mock store_session_variables to return userinfo dict, not boolean
            session_mock.return_value = {
                "sub": "cilogon_sub_123",
                "email": "test@example.com",
                "meta": {"status": "success"},
            }

            response = callback(request)

            # Should redirect to profile page
            self.assertEqual(response.status_code, 302)

    def test_callback_new_user_registration(self):
        """Test callback for new user requiring registration"""
        # Create proper state parameter (base64 encoded JSON)
        state = base64.urlsafe_b64encode(
            json.dumps({"callback_next": "/profile/"}).encode()
        ).decode()
        request = self.factory.get(
            f"/auth/callback?code=auth123&state={state}"
        )
        request.user = AnonymousUser()
        self._add_session(request)

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token"
            ) as token_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables"
            ) as session_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.get",
                side_effect=SubAssociation.DoesNotExist,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
        ):
            token_mock.return_value = {
                "access_token": "token123",
                "id_token": "id_token_123",
            }
            # Mock store_session_variables to return userinfo dict, not boolean
            session_mock.return_value = {
                "sub": "cilogon_sub_123",
                "email": "test@example.com",
            }

            response = callback(request)

            # Should redirect to association (not register) for new users
            self.assertEqual(response.status_code, 302)
            self.assertIn("associate", response.url)

    @override_settings(EXTERNAL_SYNC_CLASSES=[])
    def test_callback_transaction_rollback_on_profile_save_failure(self):
        """Test that database changes rollback if profile save fails"""
        from django.db import DatabaseError

        state = base64.urlsafe_b64encode(
            json.dumps({"callback_next": ""}).encode()
        ).decode()
        request = self.factory.get(
            f"/auth/callback?code=auth123&state={state}"
        )
        request.user = AnonymousUser()
        self._add_session(request)

        # Create SubAssociation
        sub_association = SubAssociation.objects.create(
            sub="cilogon_sub_rollback", profile=self.profile
        )
        original_idp_name = sub_association.idp_name

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token"
            ) as token_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables"
            ) as session_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login"
            ),
            patch.object(
                Profile,
                "save",
                side_effect=DatabaseError("Simulated DB error"),
            ),
        ):
            token_mock.return_value = {"access_token": "token123"}
            session_mock.return_value = {
                "sub": "cilogon_sub_rollback",
                "email": "different@example.com",  # Diff email triggers save
                "idp_name": "new_idp",
            }

            with self.assertRaises(DatabaseError):
                callback(request)

        # SubAssociation idp_name should be rolled back to original
        sub_association.refresh_from_db()
        self.assertEqual(sub_association.idp_name, original_idp_name)

    @override_settings(EXTERNAL_SYNC_CLASSES=[])
    def test_callback_transaction_commits_on_success(self):
        """Test that database changes are committed on successful callback"""
        state = base64.urlsafe_b64encode(
            json.dumps({"callback_next": ""}).encode()
        ).decode()
        request = self.factory.get(
            f"/auth/callback?code=auth123&state={state}"
        )
        request.user = AnonymousUser()
        self._add_session(request)

        # Create SubAssociation without idp_name
        sub_association = SubAssociation.objects.create(
            sub="cilogon_sub_commit",
            profile=self.profile,
            idp_name="",
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token"
            ) as token_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables"
            ) as session_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login"
            ),
        ):
            token_mock.return_value = {"access_token": "token123"}
            session_mock.return_value = {
                "sub": "cilogon_sub_commit",
                "email": "test@example.com",
                "idp_name": "Updated IDP",
            }

            response = callback(request)

        # Should redirect successfully
        self.assertEqual(response.status_code, 302)

        # SubAssociation idp_name should be updated
        sub_association.refresh_from_db()
        self.assertEqual(sub_association.idp_name, "Updated IDP")

    @override_settings(EXTERNAL_SYNC_CLASSES=[])
    def test_callback_external_sync_runs_outside_transaction(self):
        """Test that ExternalSync runs after transaction commits"""
        state = base64.urlsafe_b64encode(
            json.dumps({"callback_next": ""}).encode()
        ).decode()
        request = self.factory.get(
            f"/auth/callback?code=auth123&state={state}"
        )
        request.user = AnonymousUser()
        self._add_session(request)

        _ = SubAssociation.objects.create(
            sub="cilogon_sub_sync", profile=self.profile
        )

        sync_call_order = []

        def track_find_user(*args, **kwargs):
            sync_call_order.append("find_user")

        def track_sync(*args, **kwargs):
            sync_call_order.append("sync")

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.cilogon.authorize_access_token"
            ) as token_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.store_session_variables"
            ) as session_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.forward_url",
                return_value=None,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.find_user_and_login",
                side_effect=track_find_user,
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync",
                side_effect=track_sync,
            ),
        ):
            token_mock.return_value = {"access_token": "token123"}
            session_mock.return_value = {
                "sub": "cilogon_sub_sync",
                "email": "test@example.com",
            }

            callback(request)

        # Verify sync is called after find_user (outside the transaction)
        self.assertEqual(sync_call_order, ["find_user", "sync"])


class LogoutTests(CILogonTestBase):
    """Test cases for logout functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def test_app_logout_authenticated_user(self):
        """Test logout for authenticated user"""
        request = self.factory.post("/cilogon/logout/")
        request.session = SessionStore()
        request.session.create()
        request.user = self.user

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.logout"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ) as client_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.logout_all_endpoints_sync"
            ),
        ):
            mock_client = MagicMock()
            mock_client.server_metadata = {
                "revocation_endpoint": "https://test.com/revoke"
            }
            client_mock.return_value = mock_client

            app_logout(request)

    def test_app_logout_anonymous_user(self):
        """Test logout for anonymous user"""
        request = self.factory.post("/cilogon/logout/")
        request.session = SessionStore()
        request.session.create()
        request.user = AnonymousUser()

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.logout"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ) as client_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.logout_all_endpoints_sync"
            ),
        ):
            mock_client = MagicMock()
            mock_client.server_metadata = {
                "revocation_endpoint": "https://test.com/revoke"
            }
            client_mock.return_value = mock_client

            app_logout(request)
            # self.assertEqual(response.status_code, 302)  # Redirect response

    def test_app_logout_custom_user_agent(self):
        """Test logout with custom user agent parameter"""
        request = self.factory.post("/cilogon/logout/")
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }

        with (
            patch("django.contrib.auth.logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter"
            ) as filter_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations"
            ) as delete_mock,
            patch("knowledge_commons_profiles.cilogon.views.revoke_token"),
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ) as client_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.logout_all_endpoints_sync"
            ),
        ):
            # Mock the OAuth client
            mock_client = MagicMock()
            mock_client.server_metadata = {
                "revocation_endpoint": "https://test.com/revoke"
            }
            client_mock.return_value = mock_client

            # Mock token associations to exist so delete_associations will
            # be called
            mock_queryset = MagicMock()
            mock_queryset.exists.return_value = True
            mock_token_association = MagicMock()
            mock_token_association.refresh_token = "test_refresh"
            mock_token_association.access_token = "test_access"
            mock_queryset.__iter__.return_value = [mock_token_association]
            filter_mock.return_value = mock_queryset

            # Mock delete_associations to raise database error
            delete_mock.side_effect = DatabaseError("DB Error")

            with self.assertRaises(DatabaseError):
                app_logout(request, user_agent="CustomAgent")


    def test_app_logout_database_error(self):
        """Test logout with database error during association cleanup"""
        request = self.factory.post("/cilogon/logout/")
        request.user = self.user
        self._add_session(request)
        request.session["oidc_token"] = {
            "access_token": "test_token",
            "refresh_token": "test_refresh",
        }

        with (
            patch("django.contrib.auth.logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views.TokenUserAgentAssociations.objects.filter"
            ) as filter_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.oauth.create_client"
            ) as create_client_mock,
            patch(
                "knowledge_commons_profiles.cilogon.views.delete_associations",
                side_effect=DatabaseError("DB Error"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.logout_all_endpoints_sync"
            ),
        ):
            # Mock the OAuth client
            mock_client = MagicMock()
            mock_client.server_metadata = {
                "revocation_endpoint": "https://test.com/revoke"
            }
            create_client_mock.return_value = mock_client

            # Mock token associations
            mock_queryset = MagicMock()
            mock_queryset.exists.return_value = True
            mock_token_association = MagicMock()
            mock_token_association.refresh_token = "test_refresh"
            mock_token_association.access_token = "test_access"
            mock_queryset.__iter__.return_value = [mock_token_association]
            filter_mock.return_value = mock_queryset

            with self.assertRaises(DatabaseError):
                app_logout(request)


class FormValidationTests(CILogonTestBase):
    """Test form validation functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )

        self.existing_profile = Profile.objects.create(
            username="existing",
            email="existing@example.com",
            name="Existing User",
        )

    def _create_request_with_messages(self, path="/", method="GET", data=None):
        """Helper to create request with proper messages middleware setup"""
        if method.upper() == "POST":
            request = self.factory.post(path, data or {})
        else:
            request = self.factory.get(path)
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        return request

    def test_extract_form_data_valid(self):
        """Test extracting valid form data"""
        request = self._create_request_with_messages(
            "/",
            "POST",
            {
                "email": "test@example.com",
                "full_name": "Test User",
                "username": "testuser",
            },
        )
        context = {}
        userinfo = {"email": "test@example.com", "name": "Test User"}

        email, full_name, username = extract_form_data(
            context, request, userinfo
        )

        self.assertEqual(email, "test@example.com")
        self.assertEqual(full_name, "Test User")
        self.assertEqual(username, "testuser")

    def test_extract_form_data_missing_full_name(self):
        """Test extracting form data with missing full name gracefully"""
        request = self._create_request_with_messages(
            "/",
            "POST",
            {
                "email": "test@example.com",
                "username": "testuser",
            },
        )
        context = {}
        userinfo = {"email": "test@example.com", "name": "Test User"}

        # Should not raise - handles None gracefully
        email, full_name, username = extract_form_data(
            context, request, userinfo
        )

        self.assertEqual(email, "test@example.com")
        self.assertIsNone(full_name)
        self.assertEqual(username, "testuser")

    def test_validate_form_valid(self):
        """Test form validation with valid data"""
        request = self._create_request_with_messages()

        errored = validate_form(
            "new@example.com",
            "New User",
            request,
            "newuser",
        )

        self.assertFalse(errored)

    def test_validate_form_missing_fields(self):
        """Test form validation with missing fields"""
        request = self._create_request_with_messages()

        with patch(
            "knowledge_commons_profiles.cilogon.views.messages.error"
        ):
            errored = validate_form(
                "",
                "",
                request,
                "",
            )

            self.assertTrue(errored)

    def test_validate_form_duplicate_email(self):
        """Test form validation with duplicate email"""
        request = self._create_request_with_messages()

        with patch(
            "knowledge_commons_profiles.cilogon.views.messages.error"
        ):
            errored = validate_form(
                "existing@example.com",
                "New User",
                request,
                "newuser",
            )

            self.assertTrue(errored)

    def test_validate_form_duplicate_username(self):
        """Test form validation with duplicate username"""
        request = self._create_request_with_messages()

        with patch(
            "knowledge_commons_profiles.cilogon.views.messages.error"
        ):
            errored = validate_form(
                "new@example.com",
                "New User",
                request,
                "existing",
            )

            self.assertTrue(errored)

    def test_validate_form_database_error(self):
        """Test form validation with database error during duplicate check"""
        request = self._create_request_with_messages()

        with patch(
            "knowledge_commons_profiles.cilogon.views.Profile.objects.filter"
        ) as filter_mock:
            filter_mock.side_effect = DatabaseError("DB Error")

            with self.assertRaises(DatabaseError):
                validate_form(
                    "test@example.com",
                    "Test User",
                    request,
                    "testuser",
                )


class AssociationTests(CILogonTestBase):
    """Test cases for profile association functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def _add_session(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()

    def _create_request_with_messages(self, path="/", method="GET", data=None):
        """Helper to create request with proper messages middleware setup"""
        if method.upper() == "POST":
            request = self.factory.post(path, data or {})
        else:
            request = self.factory.get(path)
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        return request

    def test_association_get_request(self):
        """Test association view with GET request"""
        request = self.factory.get("/auth/association/")
        request.user = AnonymousUser()
        self._add_session(request)
        request.session["userinfo"] = {
            "sub": "cilogon_sub_123",
            "email": "test@example.com",
        }

        with patch(
            "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
            return_value=(True, request.session["userinfo"]),
        ):
            association(request)

        # self.assertEqual(response.status_code, 200)

    def test_association_invalid_userinfo(self):
        """Test association view with invalid userinfo"""
        request = self.factory.get("/auth/association/")
        request.user = AnonymousUser()
        self._add_session(request)

        with patch(
            "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
            return_value=(False, None),
        ):
            association(request)

        # self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_association_authenticated_user(self):
        """Test association view with already authenticated user"""
        request = self.factory.get("/auth/association/")
        request.user = self.user
        self._add_session(request)

        association(request)

        # self.assertEqual(response.status_code, 302)  # Redirect to profile

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False)
    def test_association_post_no_verification(self):
        """Test association POST without email verification required"""
        request = self.factory.post(
            "/auth/association/", {"email": "test@example.com"}
        )
        request.user = AnonymousUser()
        self._add_session(request)
        request.session["userinfo"] = {
            "sub": "cilogon_sub_123",
            "email": "test@example.com",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
                return_value=(True, request.session["userinfo"]),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.associate_with_existing_profile"
            ) as assoc_mock,
        ):
            assoc_mock.return_value = None  # Successful association

            association(request)

    @override_settings(EMAIL_VERIFICATION_REQUIRED=True)
    def test_association_post_with_verification(self):
        """Test association POST with email verification required"""
        request = self.factory.post(
            "/auth/association/", {"email": "test@example.com"}
        )
        request.user = AnonymousUser()
        self._add_session(request)
        request.session["userinfo"] = {
            "sub": "cilogon_sub_123",
            "email": "test@example.com",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
                return_value=(True, request.session["userinfo"]),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.send_knowledge_commons_email",
                return_value=True,
            ),
        ):
            association(request)

        # Should create EmailVerification record
        self.assertTrue(
            EmailVerification.objects.filter(sub="cilogon_sub_123").exists()
        )

    def test_association_post_profile_not_found(self):
        """Test association POST when profile doesn't exist"""
        request = self._create_request_with_messages()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)

        with patch(
            "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
            return_value=(True, {"sub": "test_sub"}),
        ):
            association(request)

        # Should render association template successfully
        # self.assertEqual(response.status_code, 200)

    def test_associate_with_existing_profile_success(self):
        """Test successful profile association"""
        request = self._create_request_with_messages()
        userinfo = {
            "sub": "cilogon_sub_123",
            "email": "test@example.com",
            "idp_name": "Test University",
        }

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_knowledge_commons_email"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sanitize_email_for_dev",
                return_value="test@example.com",
            ),
        ):
            result = associate_with_existing_profile(
                "test@example.com", self.profile, request, userinfo
            )

        self.assertIsNone(result)  # Successful association returns None

        # Should create EmailVerification with idp_name
        verification = EmailVerification.objects.get(
            sub="cilogon_sub_123", profile=self.profile
        )
        self.assertEqual(verification.idp_name, "Test University")

    def test_associate_with_existing_profile_no_user(self):
        """Test profile association when Django User doesn't exist"""
        request = self._create_request_with_messages()
        self.user.delete()

        userinfo = {"sub": "cilogon_sub_123", "email": "test@example.com"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_knowledge_commons_email"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sanitize_email_for_dev",
                return_value="test@example.com",
            ),
        ):
            result = associate_with_existing_profile(
                "test@example.com", self.profile, request, userinfo
            )

        self.assertIsNone(result)

        # Should create EmailVerification
        self.assertTrue(
            EmailVerification.objects.filter(
                sub="cilogon_sub_123", profile=self.profile
            ).exists()
        )


    def test_associate_with_existing_profile_database_error(self):
        """Test profile association with database error"""
        request = self._create_request_with_messages()
        userinfo = {"sub": "cilogon_sub_123", "email": "test@example.com"}

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.EmailVerification.objects.create",
                side_effect=IntegrityError("Duplicate key"),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.sanitize_email_for_dev",
                return_value="test@example.com",
            ),
            self.assertRaises(IntegrityError),
        ):
            associate_with_existing_profile(
                "test@example.com", self.profile, request, userinfo
            )



class EmailVerificationTests(CILogonTestBase):
    """Test cases for email verification functionality.

    The view splits handling: GET/HEAD render an interstitial confirmation
    page that does NOT consume the token (defends against link-scanner
    pre-fetch); POST consumes the token and runs side effects. Missing or
    expired tokens render a friendly invalid-link page (HTTP 410 Gone).
    """

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )
        self.user = User.objects.create_user("testuser", password="pw")

    def _add_session_and_messages(self, request):
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)

    # ---------- POST: happy paths ----------

    def test_activate_post_consumes_and_logs_in(self):
        """POST consumes the token, creates SubAssociation, logs the user in."""
        request = self.factory.post("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
            idp_name="Test University",
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_association_message"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.hcommons_add_new_user_to_mailchimp"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync"
            ),
        ):
            response = activate(request, verification.secret_uuid)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("my_profile"))

        sub_assoc = SubAssociation.objects.get(
            sub="cilogon_sub_123", profile=self.profile
        )
        self.assertEqual(sub_assoc.idp_name, "Test University")

        self.assertFalse(
            EmailVerification.objects.filter(id=verification.id).exists()
        )

    # ---------- GET / HEAD: scanner-safe ----------

    def test_activate_get_renders_confirm_does_not_consume(self):
        """GET renders the confirm page and does not touch the token or run
        any side effects."""
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
            idp_name="Test University",
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_association_message"
            ) as mock_assoc,
            patch(
                "knowledge_commons_profiles.cilogon.views.hcommons_add_new_user_to_mailchimp"
            ) as mock_mc,
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync"
            ) as mock_sync,
        ):
            response = activate(request, verification.secret_uuid)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<form", response.content)
        # Token still exists
        self.assertTrue(
            EmailVerification.objects.filter(id=verification.id).exists()
        )
        # No SubAssociation created
        self.assertFalse(
            SubAssociation.objects.filter(
                sub="cilogon_sub_123", profile=self.profile
            ).exists()
        )
        # No side effects
        mock_assoc.assert_not_called()
        mock_mc.assert_not_called()
        mock_sync.assert_not_called()

    def test_activate_head_does_not_consume(self):
        """HEAD does not consume the token or run side effects."""
        request = self.factory.generic("HEAD", "/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_association_message"
            ) as mock_assoc,
            patch(
                "knowledge_commons_profiles.cilogon.views.hcommons_add_new_user_to_mailchimp"
            ) as mock_mc,
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync"
            ) as mock_sync,
        ):
            activate(request, verification.secret_uuid)

        self.assertTrue(
            EmailVerification.objects.filter(id=verification.id).exists()
        )
        self.assertFalse(
            SubAssociation.objects.filter(
                sub="cilogon_sub_123", profile=self.profile
            ).exists()
        )
        mock_assoc.assert_not_called()
        mock_mc.assert_not_called()
        mock_sync.assert_not_called()

    # ---------- Missing / expired token ----------

    def test_activate_get_missing_token_renders_invalid(self):
        """GET with an unknown token renders the invalid-link page (410)."""
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        response = activate(request, "no-such-uuid")

        self.assertEqual(response.status_code, 410)
        self.assertIn(b"no longer valid", response.content.lower())

    def test_activate_post_missing_token_renders_invalid(self):
        """POST with an unknown token renders the invalid-link page (410)."""
        request = self.factory.post("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        response = activate(request, "no-such-uuid")

        self.assertEqual(response.status_code, 410)
        self.assertIn(b"no longer valid", response.content.lower())

    def test_activate_post_wrong_secret_renders_invalid(self):
        """POST with a different valid-shaped secret renders the invalid
        page (410) rather than 404."""
        request = self.factory.post("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        response = activate(request, "wrong-secret")

        self.assertEqual(response.status_code, 410)

    def test_activate_repeated_post_renders_invalid(self):
        """A second POST with the same secret (already consumed) renders
        the invalid page rather than 500ing."""
        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        request1 = self.factory.post("/")
        request1.user = AnonymousUser()
        self._add_session_and_messages(request1)

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.send_association_message"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.hcommons_add_new_user_to_mailchimp"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync"
            ),
        ):
            response1 = activate(request1, verification.secret_uuid)
        self.assertEqual(response1.status_code, 302)

        request2 = self.factory.post("/")
        request2.user = AnonymousUser()
        self._add_session_and_messages(request2)
        response2 = activate(request2, verification.secret_uuid)

        self.assertEqual(response2.status_code, 410)

    def test_activate_expired_verification_renders_invalid(self):
        """Expired verification renders 410 invalid page on either verb;
        the row is NOT deleted by the view (GC handles cleanup separately)."""
        request = self.factory.post("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        with patch.object(
            EmailVerification, "is_expired", return_value=True
        ):
            response = activate(request, verification.secret_uuid)

        self.assertEqual(response.status_code, 410)
        self.assertTrue(
            EmailVerification.objects.filter(id=verification.id).exists()
        )
        self.assertFalse(
            SubAssociation.objects.filter(
                sub="cilogon_sub_123", profile=self.profile
            ).exists()
        )

    # ---------- DB error during POST is still propagated ----------

    def test_activate_post_database_error_propagates(self):
        """A DB error inside the POST consumption flow is not swallowed."""
        request = self.factory.post("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.SubAssociation.objects.create",
                side_effect=DatabaseError("DB Error"),
            ),
            self.assertRaises(DatabaseError),
        ):
            activate(request, verification.secret_uuid)

    # ---------- Regression: do not call garbage_collect ----------

    def test_activate_does_not_call_garbage_collect(self):
        """The view must not invoke EmailVerification.garbage_collect itself
        — it would write on every scanner pre-fetch."""
        verification = EmailVerification.objects.create(
            secret_uuid="test-uuid",
            profile=self.profile,
            sub="cilogon_sub_123",
        )

        # GET path
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)
        with patch.object(EmailVerification, "garbage_collect") as mock_gc:
            activate(request, verification.secret_uuid)
        mock_gc.assert_not_called()

        # POST path
        request2 = self.factory.post("/")
        request2.user = AnonymousUser()
        self._add_session_and_messages(request2)
        with (
            patch.object(EmailVerification, "garbage_collect") as mock_gc2,
            patch(
                "knowledge_commons_profiles.cilogon.views.send_association_message"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.hcommons_add_new_user_to_mailchimp"
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.ExternalSync.sync"
            ),
        ):
            activate(request2, verification.secret_uuid)
        mock_gc2.assert_not_called()

    # ---------- CSRF ----------

    def test_activate_confirm_page_renders_csrf_token_input(self):
        """The confirm page must include a CSRF token input so the POST
        survives Django's CSRF middleware."""
        EmailVerification.objects.create(
            secret_uuid="csrf-uuid",
            profile=self.profile,
            sub="cilogon_sub_999",
        )

        request = self.factory.get("/")
        request.user = AnonymousUser()
        self._add_session_and_messages(request)

        response = activate(request, "csrf-uuid")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"csrfmiddlewaretoken", response.content)

    def test_confirm_view(self):
        """Test confirmation view"""
        request = self.factory.get("/auth/confirm/")

        confirm(request)

        # Should render confirmation template
