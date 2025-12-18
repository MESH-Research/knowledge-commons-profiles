"""
Comprehensive unit tests for CILogon OAuth functionality
"""

import base64
import json
import time
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from authlib.jose.errors import InvalidClaimError
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import SecureParamEncoder
from knowledge_commons_profiles.cilogon.oauth import (
    check_for_sub_or_return_negative,
)
from knowledge_commons_profiles.cilogon.oauth import delete_associations
from knowledge_commons_profiles.cilogon.oauth import extract_code_next_url
from knowledge_commons_profiles.cilogon.oauth import find_user_and_login
from knowledge_commons_profiles.cilogon.oauth import generate_next_url
from knowledge_commons_profiles.cilogon.oauth import get_cilogon_jwks
from knowledge_commons_profiles.cilogon.oauth import pack_state
from knowledge_commons_profiles.cilogon.oauth import revoke_token
from knowledge_commons_profiles.cilogon.oauth import send_association_message
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.cilogon.oauth import token_expired
from knowledge_commons_profiles.cilogon.oauth import (
    verify_and_decode_cilogon_jwt,
)
from knowledge_commons_profiles.newprofile.models import Profile

from .test_base import CILogonTestBase


class ORCIDHandledTokenTests(CILogonTestBase):
    """Test cases for ORCID token validation fixes"""

    def setUp(self):
        # ORCIDHandledToken requires payload and header parameters
        self.payload = {
            "amr": "password",
            "sub": "user123",
            "iss": "cilogon.org",
        }
        self.header = {"alg": "RS256", "typ": "JWT"}

    def test_validate_amr_with_string_value(self):
        """Test that AMR validation handles string values from ORCID"""
        # ORCID sends AMR as string instead of array
        payload = {"amr": "password", "sub": "user123", "iss": "cilogon.org"}
        header = {"alg": "RS256", "typ": "JWT"}

        token = ORCIDHandledToken(payload, header)

        # Should not raise an exception
        try:
            token.validate_amr()
        except InvalidClaimError:
            self.fail("validate_amr raised InvalidClaimError unexpectedly")

    def test_validate_amr_with_array_value(self):
        """Test that AMR validation handles standard array values"""
        payload = {
            "amr": ["password", "otp"],
            "sub": "user123",
            "iss": "cilogon.org",
        }
        header = {"alg": "RS256", "typ": "JWT"}

        token = ORCIDHandledToken(payload, header)

        # Should not raise an exception
        try:
            token.validate_amr()
        except InvalidClaimError:
            self.fail("validate_amr raised InvalidClaimError unexpectedly")

    def test_validate_amr_with_none_value(self):
        """Test that AMR validation handles None values"""
        payload = {"amr": None, "sub": "user123", "iss": "cilogon.org"}
        header = {"alg": "RS256", "typ": "JWT"}

        token = ORCIDHandledToken(payload, header)

        # Should not raise an exception
        try:
            token.validate_amr()
        except InvalidClaimError:
            self.fail("validate_amr raised InvalidClaimError unexpectedly")

    def test_validate_amr_missing_claim(self):
        """Test that AMR validation handles missing AMR claim"""
        payload = {"sub": "user123", "iss": "cilogon.org"}
        header = {"alg": "RS256", "typ": "JWT"}

        token = ORCIDHandledToken(payload, header)

        # Should not raise an exception
        try:
            token.validate_amr()
        except InvalidClaimError:
            self.fail("validate_amr raised InvalidClaimError unexpectedly")

    def test_validate_amr_invalid_type(self):
        """Test that AMR validation rejects invalid types"""
        payload = {
            "amr": 123,
            "sub": "user123",
            "iss": "cilogon.org",
        }  # Invalid type
        header = {"alg": "RS256", "typ": "JWT"}

        token = ORCIDHandledToken(payload, header)

        # Should raise InvalidClaimError for invalid type
        with self.assertRaises(InvalidClaimError):
            token.validate_amr()


class URLUtilityTests(CILogonTestBase):
    """Test cases for URL utility functions"""

    def setUp(self):
        self.factory = RequestFactory()

    def test_pack_state_valid_url(self):
        """Test packing a valid URL into state parameter"""
        url = "https://example.com/profile"
        packed = pack_state(url)

        # Should be base64 encoded
        self.assertIsInstance(packed, str)

        # Should be decodable to JSON with callback_next key
        decoded_json = base64.b64decode(packed).decode()
        decoded_data = json.loads(decoded_json)
        self.assertEqual(decoded_data["callback_next"], url)

    def test_pack_state_empty_url(self):
        """Test packing an empty URL"""
        packed = pack_state("")
        decoded_json = base64.b64decode(packed).decode()
        decoded_data = json.loads(decoded_json)
        self.assertEqual(decoded_data["callback_next"], "")

    def test_pack_state_invalid_url(self):
        """Test packing an invalid URL"""
        with self.assertRaises(ValueError):
            pack_state("jlsdlfd432324BLEURGH")

    def test_generate_next_url_with_existing_params(self):
        """Test generating next URL with existing query parameters"""
        request = self.factory.get("/callback?existing=param")
        code = "auth_code_123"
        next_url = "https://example.com/profile?user=test"

        result = generate_next_url(code, next_url, request)

        # Function returns URL parts list, not a complete URL string
        self.assertIsInstance(result, list)
        self.assertEqual(
            len(result), 6
        )  # URL parts: scheme, netloc, path, params, query, fragment

        # Check that query string contains expected parameters
        query_string = result[4]  # Query is at index 4
        self.assertIn("code=auth_code_123", query_string)
        self.assertIn("user=test", query_string)

    def test_extract_code_next_url_valid_request(self):
        """Test extracting code and next URL from valid callback request"""
        # Create a proper state parameter using pack_state
        next_url = "https://example.com/profile"
        state = pack_state(next_url)

        request = self.factory.get(f"/callback?code=auth123&state={state}")

        code, extracted_next_url = extract_code_next_url(request)

        self.assertEqual(code, "auth123")
        self.assertEqual(extracted_next_url, next_url)

    def test_generate_next_url_no_existing_params(self):
        """Test generating next URL without existing query parameters"""
        request = self.factory.get("/callback")
        code = "auth_code_123"
        next_url = "https://example.com/profile"

        result = generate_next_url(code, next_url, request)

        # Function returns URL parts list
        self.assertIsInstance(result, list)
        query_string = result[4]
        self.assertIn("code=auth_code_123", query_string)

    def test_extract_code_state_is_none(self):
        """Test for when state is None"""
        # Create a proper state parameter
        request = self.factory.get("/callback")

        code, next_url = extract_code_next_url(request)

        self.assertIsNone(code)
        self.assertEqual(next_url, None)

    def test_extract_code_next_url_missing_code(self):
        """Test extracting from request missing authorization code"""
        # Create a proper state parameter
        state = pack_state("https://example.com/profile")
        request = self.factory.get(f"/callback?state={state}")

        code, next_url = extract_code_next_url(request)

        self.assertIsNone(code)
        self.assertEqual(next_url, "https://example.com/profile")

    def test_extract_code_next_url_invalid_state(self):
        """Test extracting from request with invalid base64 state"""
        request = self.factory.get(
            "/callback?code=auth123&state=invalid_base64!"
        )

        # Should handle invalid base64 gracefully
        with self.assertRaises((ValueError, json.JSONDecodeError, Exception)):
            extract_code_next_url(request)

    def test_extract_code_next_url_missing_state(self):
        """Test extracting from request missing state parameter"""
        request = self.factory.get("/callback?code=auth123")

        code, next_url = extract_code_next_url(request)

        # Should handle missing state gracefully
        self.assertIsNone(code)
        self.assertIsNone(next_url)


class TokenManagementTests(CILogonTestBase):
    """Test cases for token management functionality"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")

    def test_token_expired_with_expired_token(self):
        """Test token expiration check with expired token"""
        # Create token that expired 1 hour ago
        expired_time = int(time.time()) - 3600
        token = {"expires_at": expired_time}

        self.assertTrue(token_expired(token, self.user))

    def test_token_expired_with_valid_token(self):
        """Test token expiration check with valid token"""
        # Create token that expires in 1 hour
        future_time = int(time.time()) + 3600
        token = {"expires_at": future_time}

        self.assertFalse(token_expired(token, self.user))

    def test_token_expired_missing_exp_claim(self):
        """Test token expiration check with missing expires_at claim"""
        token = {"sub": "user123"}

        # Should return True for safety when expires_at claim is missing
        self.assertTrue(token_expired(token, self.user))

    def test_revoke_token_success(self):
        """Test successful token revocation"""
        client = Mock()
        client.post.return_value = Mock(status_code=200)
        revocation_url = "https://test.cilogon.org/oauth2/revoke"
        token_with_privilege = "access_token_123"
        token_revoke = {
            "refresh_token": "refresh_token_456",
            "access_token": "access_token_789",
        }

        result = revoke_token(
            client, revocation_url, token_with_privilege, token_revoke
        )

        self.assertIsNone(result)
        # Should call client.post twice (once for refresh_token,
        # once for access_token)
        self.assertEqual(client.post.call_count, 2)

    def test_revoke_token_failure(self):
        """Test failed token revocation"""
        client = Mock()
        client.post.return_value = Mock(status_code=400, text="Invalid token")
        revocation_url = "https://test.cilogon.org/oauth2/revoke"
        token_with_privilege = "access_token_123"
        token_revoke = {
            "refresh_token": "refresh_token_456",
            "access_token": "access_token_789",
        }

        result = revoke_token(
            client, revocation_url, token_with_privilege, token_revoke
        )

        self.assertIsNone(result)
        # Should still call client.post even on failure
        self.assertEqual(client.post.call_count, 2)


class AssociationManagementTests(CILogonTestBase):
    """Test cases for user association management"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", password="pw")
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def test_delete_associations_success(self):
        """Test successful deletion of token associations"""
        # Create mock associations queryset
        mock_associations = MagicMock()
        mock_associations.delete.return_value = None

        # delete_associations doesn't return a value, just executes
        result = delete_associations(mock_associations)

        # Function doesn't return anything, just check it executed
        self.assertIsNone(result)
        mock_associations.delete.assert_called_once()

    def test_delete_associations_protected_error(self):
        """Test deletion with protected foreign key error"""

        mock_associations = MagicMock()
        mock_associations.delete.side_effect = ProtectedError(
            "Cannot delete", set()
        )

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.logger"
        ) as mock_logger:
            result = delete_associations(mock_associations)

            # Should handle ProtectedError gracefully
            self.assertIsNone(result)
            mock_logger.warning.assert_called_once()

    def test_delete_associations_integrity_error(self):
        """Test deletion with database integrity error"""
        mock_associations = MagicMock()
        mock_associations.delete.side_effect = IntegrityError(
            "Integrity error"
        )

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.logger"
        ) as mock_logger:
            result = delete_associations(mock_associations)

            # Function handles exception and logs warning
            self.assertIsNone(result)
            mock_logger.warning.assert_called_once()

    def test_find_user_and_login_success(self):
        """Test successful user lookup and login"""

        # Create a proper Django request with session
        request = self.factory.get("/")
        session = SessionStore()
        session.create()
        request.session = session

        # Create test user and profile, then association
        User.objects.create_user(
            "testuser_success", email="test@example.com", password="pw"
        )
        Profile.objects.create(
            username="testuser_success", email="test@example.com"
        )
        sub_association = SubAssociation.objects.create(
            profile=Profile.objects.get(username="testuser_success"),
            sub="test_sub_success",
        )

        with patch("knowledge_commons_profiles.cilogon.oauth.logger"):
            result = find_user_and_login(request, sub_association)
            # Function returns None on success
            self.assertIsNone(result)

    def test_find_user_and_login_no_user(self):
        """Test user lookup when Django User doesn't exist"""

        # Create a proper Django request with session
        request = self.factory.get("/")
        session = SessionStore()
        session.create()
        request.session = session

        # Create profile and association but no Django user
        profile = Profile.objects.create(
            username="testuser_nouser", email="test2@example.com"
        )
        sub_association = SubAssociation.objects.create(
            profile=profile,
            sub="test_sub_nouser",
        )

        with patch("knowledge_commons_profiles.cilogon.oauth.logger"):
            result = find_user_and_login(request, sub_association)
            # Function creates the user and logs them in, returns None
            self.assertIsNone(result)

        # Verify that a Django user was created
        created_user = User.objects.filter(username="testuser_nouser").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.email, "test2@example.com")


class SecureParamEncoderTests(TestCase):
    """Test cases for secure parameter encoding/decoding"""

    def setUp(self):
        self.encoder = SecureParamEncoder("test_secret_key_123")

    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding data roundtrip"""
        data = {"user_id": "123", "redirect_url": "https://example.com"}

        encoded = self.encoder.encode(data)
        decoded = self.encoder.decode(encoded)

        self.assertEqual(data, decoded)

    def test_encode_empty_data(self):
        """Test encoding empty data"""
        data = {}

        encoded = self.encoder.encode(data)
        decoded = self.encoder.decode(encoded)

        self.assertEqual(data, decoded)

    def test_decode_invalid_data(self):
        """Test decoding invalid encrypted data"""
        invalid_data = "not_valid_encrypted_data"

        with self.assertRaises((ValueError, Exception)):
            self.encoder.decode(invalid_data)

    def test_different_keys_incompatible(self):
        """Test that different encryption keys are incompatible"""
        encoder1 = SecureParamEncoder("secret1")
        encoder2 = SecureParamEncoder("secret2")

        data = {"test": "value"}
        encoded = encoder1.encode(data)

        with self.assertRaises((ValueError, Exception)):
            encoder2.decode(encoded)


class UserInfoValidationTests(TestCase):
    """Test cases for user info validation"""

    def test_check_for_sub_valid_userinfo(self):
        """Test checking for sub with valid userinfo"""
        userinfo = {"sub": "cilogon_sub_123", "email": "test@example.com"}

        is_valid, result = check_for_sub_or_return_negative(userinfo)

        self.assertTrue(is_valid)
        self.assertEqual(result, userinfo)

    def test_check_for_sub_missing_sub(self):
        """Test checking for sub with missing sub claim"""
        userinfo = {"email": "test@example.com", "name": "Test User"}

        is_valid, result = check_for_sub_or_return_negative(userinfo)

        self.assertFalse(is_valid)
        self.assertIsNone(result)

    def test_check_for_sub_empty_sub(self):
        """Test checking for sub with empty sub claim"""
        userinfo = {"sub": "", "email": "test@example.com"}

        is_valid, result = check_for_sub_or_return_negative(userinfo)

        self.assertFalse(is_valid)
        self.assertIsNone(result)

    def test_check_for_sub_empty_userinfo(self):
        """Test checking for sub with empty userinfo"""
        userinfo = {}

        is_valid, result = check_for_sub_or_return_negative(userinfo)

        self.assertFalse(is_valid)
        self.assertIsNone(result)


class JWTValidationTests(CILogonTestBase):
    """Test cases for JWT validation functionality"""

    @patch("knowledge_commons_profiles.cilogon.oauth.cache.get")
    def test_get_cilogon_jwks_cached(self, mock_cache_get):
        """Test getting JWKS from cache"""
        cached_jwks = {"keys": [{"kid": "test", "kty": "RSA"}]}
        mock_cache_get.return_value = cached_jwks

        result = get_cilogon_jwks()

        self.assertEqual(result, cached_jwks)
        mock_cache_get.assert_called_once_with("cilogon_jwks")

    @patch("knowledge_commons_profiles.cilogon.oauth.cache.get")
    @patch("knowledge_commons_profiles.cilogon.oauth.cache.set")
    @patch("knowledge_commons_profiles.cilogon.oauth.requests.get")
    def test_get_cilogon_jwks_fetch_and_cache(
        self, mock_get, mock_cache_set, mock_cache_get
    ):
        """Test fetching JWKS from CILogon and caching"""
        mock_cache_get.return_value = None

        # Mock successful response from CILogon
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "keys": [{"kid": "test", "kty": "RSA"}]
        }
        mock_get.return_value = mock_response

        result = get_cilogon_jwks()

        self.assertEqual(result, {"keys": [{"kid": "test", "kty": "RSA"}]})
        mock_cache_set.assert_called_once()

    @patch("knowledge_commons_profiles.cilogon.oauth.get_cilogon_jwks")
    def test_verify_and_decode_cilogon_jwt_success(self, mock_get_jwks):
        """Test successful JWT verification and decoding"""
        # Create a proper JWT token for testing

        # Mock JWKS response
        mock_jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-key-id",
                    "use": "sig",
                    "n": "test-modulus",
                    "e": "AQAB",
                }
            ]
        }
        mock_get_jwks.return_value = mock_jwks

        # Create a test payload
        payload = {
            "sub": "user123",
            "iss": "https://cilogon.org",
            "aud": "test-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "amr": ["pwd"],
        }

        # Create a test JWT (this will be decoded by the mocked JWT library)
        test_token = (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiJ1c2VyMTIzIiwiaXNzIjoiaHR0cHM6Ly9jaWxvZ29uLm9yZyIs"
            "ImF1ZCI6InRlc3QtY2xpZW50IiwiZXhwIjoxNjkwMDAwMDAwLCJpYXQiOjE2"
            "ODk5OTk5OTksImFtciI6WyJwd2QiXX0.signature"
        )

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.jwt.decode"
        ) as mock_decode:
            mock_decode.return_value = payload

            result = verify_and_decode_cilogon_jwt(test_token)

            self.assertEqual(result, payload)
            mock_decode.assert_called_once()

    @patch("knowledge_commons_profiles.cilogon.oauth.get_cilogon_jwks")
    def test_verify_and_decode_cilogon_jwt_no_jwks(self, mock_get_jwks):
        """Test JWT verification when JWKS fetch fails"""
        mock_get_jwks.return_value = None

        # Use a simpler test token that won't cause base64 padding issues
        test_token = "invalid.jwt.token"

        # Since verify_and_decode_cilogon_jwt now returns None for invalid JWTs
        # instead of raising exceptions, we should expect None
        result = verify_and_decode_cilogon_jwt(test_token)
        self.assertIsNone(result)

    @patch("knowledge_commons_profiles.cilogon.oauth.get_cilogon_jwks")
    def test_verify_and_decode_cilogon_jwt_invalid_token(self, mock_get_jwks):
        """Test JWT verification with invalid token format"""
        mock_jwks = {"keys": []}
        mock_get_jwks.return_value = mock_jwks

        # Use an obviously invalid token
        invalid_token = "not.a.jwt"

        # Since verify_and_decode_cilogon_jwt now returns None for invalid JWTs
        # instead of raising exceptions, we should expect None
        result = verify_and_decode_cilogon_jwt(invalid_token)
        self.assertIsNone(result)


class SessionManagementTests(CILogonTestBase):
    """Test cases for session management functionality"""

    def setUp(self):
        self.factory = RequestFactory()

    def test_store_session_variables_success(self):
        """Test storing session variables successfully"""
        request = self.factory.get("/")
        request.session = {}

        # Don't include userinfo in token to test the userinfo parameter
        token = {"access_token": "token123"}
        userinfo = {"sub": "user123", "email": "test@example.com"}

        result = store_session_variables(request, token, userinfo)

        # Function stores in oidc_userinfo, not userinfo
        self.assertEqual(request.session["oidc_userinfo"], userinfo)
        self.assertEqual(request.session["oidc_token"], token)
        self.assertEqual(result, userinfo)

    def test_store_session_variables_no_userinfo(self):
        """Test storing session variables without userinfo parameter"""
        request = self.factory.get("/")
        request.session = {}

        token = {"access_token": "token123"}

        result = store_session_variables(request, token, None)

        # Function returns userinfo from token or session, None if neither
        # exists
        self.assertEqual(request.session["oidc_token"], token)
        self.assertIsNone(result)

    def test_store_session_variables_from_token(self):
        """Test storing session variables from token userinfo"""
        request = self.factory.get("/")
        request.session = {}

        userinfo_in_token = {"sub": "user123", "email": "test@example.com"}
        token = {"access_token": "token123", "userinfo": userinfo_in_token}

        result = store_session_variables(request, token, None)

        # Should use userinfo from token
        self.assertEqual(request.session["oidc_userinfo"], userinfo_in_token)
        self.assertEqual(result, userinfo_in_token)


@override_settings(
    IDMS_API_BASE_URL="https://test-api.example.com",
    IDMS_API_KEY="test_api_key",
)
class AssociationMessageTests(CILogonTestBase):
    """Test cases for association message sending"""

    @patch("knowledge_commons_profiles.cilogon.oauth.APIClient")
    def test_send_association_message_success(self, mock_api_client):
        """Test successful association message sending"""
        # Mock the API client and response
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"status": "success"}
        mock_client_instance.send_association.return_value = mock_response
        mock_api_client.return_value = mock_client_instance

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.settings"
        ) as mock_settings:
            mock_settings.WORKS_UPDATE_ENDPOINTS = ["https://api.example.com"]
            mock_settings.WEBHOOK_TOKEN = "test_token"

            result = send_association_message("sub123", "kc456")

            # Function returns None on success (early return in else clause)
            self.assertIsNone(result)
            mock_client_instance.send_association.assert_called_once()

    @patch("knowledge_commons_profiles.cilogon.oauth.APIClient")
    def test_send_association_message_failure(self, mock_api_client):
        """Test failed association message sending"""
        # Mock the API client to raise an exception
        mock_client_instance = MagicMock()
        mock_client_instance.send_association.side_effect = ValueError(
            "API Error"
        )
        mock_api_client.return_value = mock_client_instance

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.settings"
        ) as mock_settings:
            mock_settings.WORKS_UPDATE_ENDPOINTS = ["https://api.example.com"]
            mock_settings.WEBHOOK_TOKEN = "test_token"

            with patch(
                "knowledge_commons_profiles.cilogon.oauth.logger"
            ) as mock_logger:
                result = send_association_message("sub123", "kc456")

                # Function returns None after handling exception
                self.assertIsNone(result)
                mock_logger.exception.assert_called_once()

    @patch("knowledge_commons_profiles.cilogon.oauth.APIClient")
    def test_send_association_message_no_endpoints(self, mock_api_client):
        """Test association message sending with no endpoints configured"""
        with patch(
            "knowledge_commons_profiles.cilogon.oauth.settings"
        ) as mock_settings:
            mock_settings.WORKS_UPDATE_ENDPOINTS = []

            result = send_association_message("sub123", "kc456")

            # Function returns None when no endpoints to process
            self.assertIsNone(result)
            mock_api_client.assert_not_called()
