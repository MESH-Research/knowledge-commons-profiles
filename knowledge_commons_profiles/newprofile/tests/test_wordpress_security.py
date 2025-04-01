import hashlib
import hmac
import math
from unittest import mock
from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.custom_login import DAY_IN_SECONDS
from knowledge_commons_profiles.newprofile.custom_login import get_login_url
from knowledge_commons_profiles.newprofile.custom_login import (
    get_wp_session_token,
)
from knowledge_commons_profiles.newprofile.custom_login import login_required
from knowledge_commons_profiles.newprofile.custom_login import wp_create_nonce
from knowledge_commons_profiles.newprofile.custom_login import wp_hash
from knowledge_commons_profiles.newprofile.custom_login import wp_nonce_tick
from knowledge_commons_profiles.newprofile.middleware import (
    WordPressAuthMiddleware,
)


class MockWordPressUser:
    """A mock WordPress user object for testing."""

    def __init__(self, id_param=1):
        self.id = id_param


class WordPressCompatibilityTestCase(TestCase):
    """Tests for WordPress compatibility functions."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )
        self.anonymous_user = AnonymousUser()
        self.request = self.factory.get("/")
        self.request.user = self.user

    def test_get_wp_session_token_success(self):
        """Test successful retrieval of WordPress session token from cookie."""
        test_cookie = "testuser|1743697830|test_session_token|hash_value"

        with mock.patch.object(
            WordPressAuthMiddleware,
            "get_wordpress_cookie",
            return_value=test_cookie,
        ):
            token = get_wp_session_token(self.request)
            self.assertEqual(token, "test_session_token")

    def test_get_wp_session_token_failure(self):
        """Test handling of invalid or missing WordPress auth cookie."""
        with mock.patch.object(
            WordPressAuthMiddleware,
            "get_wordpress_cookie",
            side_effect=IndexError("Cookie not found"),
        ):
            token = get_wp_session_token(self.request)
            self.assertIsNone(token)

    def test_wp_nonce_tick(self):
        """Test that wp_nonce_tick returns the expected value based
        on current time."""
        current_time = (
            1617235200  # Example timestamp: March 31, 2021 12:00:00 UTC
        )

        with mock.patch("time.time", return_value=current_time):
            expected_tick = math.ceil(current_time / (DAY_IN_SECONDS / 2))
            actual_tick = wp_nonce_tick()
            self.assertEqual(actual_tick, expected_tick)

    @override_settings()
    def test_wp_hash(self):
        """Test wp_hash function with a known salt and input."""
        test_salt = "test_salt_value"
        test_data = "test_data"
        expected_hash = hmac.new(
            test_salt.encode("utf-8"), test_data.encode("utf-8"), hashlib.md5
        ).hexdigest()

        with mock.patch(
            "knowledge_commons_profiles.newprofile.custom_login.env.str",
            return_value=test_salt,
        ):
            actual_hash = wp_hash(test_data)
            self.assertEqual(actual_hash, expected_hash)

    def test_wp_create_nonce(self):
        """Test creation of WordPress nonce."""
        test_uid = 42
        test_token = "test_token_12345"
        test_action = "custom_action"
        current_time = 1617235200  # Example timestamp
        nonce_tick = math.ceil(current_time / (DAY_IN_SECONDS / 2))

        # Calculate expected hash
        nonce_str = f"{nonce_tick}|{test_action}|{test_uid}|{test_token}"
        test_salt = "nonce_salt_for_testing"
        expected_hash = hmac.new(
            test_salt.encode("utf-8"), nonce_str.encode("utf-8"), hashlib.md5
        ).hexdigest()
        expected_nonce = expected_hash[
            -12:-2
        ]  # Get the expected 10-char nonce

        # Setup mocks
        mock_api = mock.MagicMock()
        mock_api.wp_user = MockWordPressUser(id_param=test_uid)

        with (
            mock.patch("time.time", return_value=current_time),
            mock.patch(
                "knowledge_commons_profiles.newprofile.custom_login.API",
                return_value=mock_api,
            ),
            mock.patch(
                "knowledge_commons_profiles.newprofile."
                "custom_login.get_wp_session_token",
                return_value=test_token,
            ),
            mock.patch(
                "knowledge_commons_profiles.newprofile."
                "custom_login.wp_hash",
                return_value=expected_hash,
            ),
        ):

            actual_nonce = wp_create_nonce(
                action=test_action, request=self.request
            )
            self.assertEqual(actual_nonce, expected_nonce)

    def test_get_login_url_without_next(self):
        """Test get_login_url without a next URL parameter."""
        with mock.patch.object(settings, "LOGIN_URL", "/custom-login/"):
            login_url = get_login_url()
            self.assertEqual(login_url, "/custom-login/")

    def test_get_login_url_with_next(self):
        """Test get_login_url with a next URL parameter."""
        next_url = "/dashboard/"

        with (
            mock.patch.object(settings, "LOGIN_URL", "/custom-login/"),
            mock.patch.object(settings, "REDIRECT_FIELD_NAME", "redirect_to"),
        ):

            login_url = get_login_url(next_url)
            parsed_url = urlparse(login_url)
            query_params = parse_qs(parsed_url.query)

            self.assertEqual(parsed_url.path, "/custom-login/")
            self.assertIn("redirect_to", query_params)
            self.assertEqual(query_params["redirect_to"][0], next_url)

    def test_login_required_authenticated(self):
        """Test login_required decorator with authenticated user."""

        @login_required
        def test_view(request):
            return HttpResponse("Success")

        self.request.user = self.user
        response = test_view(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Success")

    def test_login_required_unauthenticated(self):
        """Test login_required decorator with unauthenticated user."""

        @login_required
        def test_view(request):
            return HttpResponse("Success")

        self.request.user = self.anonymous_user

        mock_login_url = "/test-login/?redirect_to=/current-path/"
        with (
            mock.patch(
                "knowledge_commons_profiles.newprofile."
                "custom_login.get_login_url",
                return_value=mock_login_url,
            ),
            mock.patch.object(
                self.request,
                "build_absolute_uri",
                return_value="/current-path/",
            ),
        ):

            response = test_view(self.request)

            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertEqual(response.url, mock_login_url)


class WordPressCompatibilityIntegrationTestCase(TestCase):
    """Integration tests for WordPress compatibility functions."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword",
        )
        self.request = self.factory.get("/")
        self.anonymous_user = AnonymousUser()
        self.request.user = self.user

    @override_settings(
        LOGIN_URL="/wordpress-login/", REDIRECT_FIELD_NAME="redirect_to"
    )
    def test_login_flow_integration(self):
        """Test the complete login flow with custom redirect parameter."""

        @login_required
        def protected_view(request):
            return HttpResponse("Protected content")

        # Test unauthenticated access
        self.request.user = self.anonymous_user
        with mock.patch.object(
            self.request, "build_absolute_uri", return_value="/protected-page/"
        ):
            response = protected_view(self.request)

            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertTrue(response.url.startswith("/wordpress-login/"))
            self.assertIn("redirect_to=%2Fprotected-page%2F", response.url)

        # Test authenticated access
        self.request.user = self.user
        response = protected_view(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Protected content")
