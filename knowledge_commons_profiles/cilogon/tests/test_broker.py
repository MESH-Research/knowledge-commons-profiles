"""
Tests for the identity broker flow.

Tests that Profiles can act as an identity broker: exchanging CILogon
authorization codes and passing encrypted userinfo to third-party apps.
"""

import json
from unittest.mock import MagicMock
from unittest.mock import patch
from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import SecureParamEncoder
from knowledge_commons_profiles.cilogon.oauth import build_broker_redirect
from knowledge_commons_profiles.cilogon.oauth import validate_return_to
from knowledge_commons_profiles.cilogon.tests.test_base import CILogonTestBase
from knowledge_commons_profiles.newprofile.models import Profile

BROKER_SETTINGS = {
    "wordpress": {
        "name": "WordPress",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "localhost", "lndo.site"],
    },
    "works": {
        "name": "Works",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "localhost", "lndo.site"],
    },
}

TEST_SHARED_SECRET = "test-shared-secret-for-broker"


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestValidateReturnTo(TestCase):
    """Tests for validate_return_to()."""

    def test_allowed_domain_accepted(self):
        self.assertTrue(
            validate_return_to("https://hcommons.org/broker-callback/")
        )

    def test_subdomain_of_allowed_domain_accepted(self):
        self.assertTrue(
            validate_return_to(
                "https://wordpress.hcommons.org/broker-callback/"
            )
        )

    def test_unknown_domain_rejected(self):
        self.assertFalse(
            validate_return_to("https://evil.example.com/broker-callback/")
        )

    def test_empty_string_rejected(self):
        self.assertFalse(validate_return_to(""))

    def test_none_rejected(self):
        self.assertFalse(validate_return_to(None))

    def test_localhost_accepted(self):
        self.assertTrue(
            validate_return_to("https://localhost/broker-callback/")
        )

    def test_lndo_site_accepted(self):
        self.assertTrue(
            validate_return_to("https://profiles.lndo.site/broker-callback/")
        )


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestBuildBrokerRedirect(TestCase):
    """Tests for build_broker_redirect()."""

    def setUp(self):
        super().setUp()
        self.profile = MagicMock(spec=Profile)
        self.profile.username = "testuser"
        self.userinfo = {
            "sub": "http://cilogon.org/serverA/users/12345",
            "email": "test@example.com",
            "name": "Test User",
            "idp_name": "Test University",
        }
        self.return_to = "https://hcommons.org/broker-callback/"
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_returns_url_with_broker_token(self):
        result = build_broker_redirect(
            self.userinfo, self.return_to, self.profile
        )
        self.assertIsNotNone(result)
        self.assertIn("broker_token=", result)
        self.assertTrue(result.startswith("https://hcommons.org/"))

    def test_payload_structure(self):
        result = build_broker_redirect(
            self.userinfo, self.return_to, self.profile
        )
        # Extract and decrypt the token
        parsed = urlparse(result)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]

        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)

        self.assertIn("userinfo", payload)
        self.assertIn("kc_username", payload)
        self.assertIn("nonce", payload)
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertEqual(payload["kc_username"], "testuser")
        self.assertEqual(
            payload["userinfo"]["sub"],
            "http://cilogon.org/serverA/users/12345",
        )
        self.assertEqual(payload["userinfo"]["email"], "test@example.com")

    def test_nonce_stored_in_cache(self):
        result = build_broker_redirect(
            self.userinfo, self.return_to, self.profile
        )
        # Extract the nonce from the payload
        parsed = urlparse(result)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]

        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)
        nonce = payload["nonce"]

        cache_data = cache.get(f"broker_nonce:{nonce}")
        self.assertIsNotNone(cache_data)
        self.assertFalse(cache_data["used"])
        self.assertEqual(
            cache_data["sub"], "http://cilogon.org/serverA/users/12345"
        )

    def test_expiry_set_correctly(self):
        result = build_broker_redirect(
            self.userinfo, self.return_to, self.profile
        )
        parsed = urlparse(result)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]

        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)

        self.assertAlmostEqual(
            payload["exp"] - payload["iat"], 60, delta=1
        )

    def test_returns_none_for_missing_userinfo(self):
        self.assertIsNone(
            build_broker_redirect(None, self.return_to, self.profile)
        )

    def test_returns_none_for_missing_return_to(self):
        self.assertIsNone(
            build_broker_redirect(self.userinfo, "", self.profile)
        )

    def test_returns_none_for_missing_profile(self):
        self.assertIsNone(
            build_broker_redirect(self.userinfo, self.return_to, None)
        )


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestVerifyBrokerNonce(TestCase):
    """Tests for the verify_broker_nonce endpoint."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _make_request(self, nonce, bearer=TEST_SHARED_SECRET):
        return self.client.post(
            "/broker/verify-nonce/",
            data=json.dumps({"nonce": nonce}),
            content_type="application/json",
            headers={"authorization": f"Bearer {bearer}"}
        )

    def test_valid_nonce_returns_200(self):
        cache.set(
            "broker_nonce:test-nonce-123",
            {"used": False, "sub": "http://cilogon.org/serverA/users/12345"},
            timeout=60,
        )
        response = self._make_request("test-nonce-123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valid"])
        self.assertEqual(
            data["sub"], "http://cilogon.org/serverA/users/12345"
        )

    def test_nonce_consumed_after_verification(self):
        cache.set(
            "broker_nonce:test-nonce-456",
            {"used": False, "sub": "http://cilogon.org/serverA/users/12345"},
            timeout=60,
        )
        # First use succeeds
        response = self._make_request("test-nonce-456")
        self.assertEqual(response.status_code, 200)

        # Second use fails (replay rejected)
        response = self._make_request("test-nonce-456")
        self.assertEqual(response.status_code, 410)

    def test_expired_nonce_returns_410(self):
        # Don't set any cache entry — simulates expiry
        response = self._make_request("expired-nonce")
        self.assertEqual(response.status_code, 410)

    def test_missing_auth_returns_401(self):
        response = self.client.post(
            "/broker/verify-nonce/",
            data=json.dumps({"nonce": "test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_bad_bearer_returns_401(self):
        response = self._make_request("test", bearer="wrong-secret")
        self.assertEqual(response.status_code, 401)

    def test_missing_nonce_returns_400(self):
        response = self.client.post(
            "/broker/verify-nonce/",
            data=json.dumps({}),
            content_type="application/json",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"}
        )
        self.assertEqual(response.status_code, 400)

    def test_csrf_exempt_no_403(self):
        """POST with valid auth but no CSRF token must not return 403."""
        cache.set(
            "broker_nonce:csrf-test-nonce",
            {"used": False, "sub": "http://cilogon.org/serverA/users/12345"},
            timeout=60,
        )
        csrf_client = self.client_class(enforce_csrf_checks=True)
        response = csrf_client.post(
            "/broker/verify-nonce/",
            data=json.dumps({"nonce": "csrf-test-nonce"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(response.status_code, 200)

    def test_get_method_not_allowed(self):
        response = self.client.get(
            "/broker/verify-nonce/",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"}
        )
        self.assertEqual(response.status_code, 405)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestSilentLogin(TestCase):
    """Tests for the silent_login endpoint."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com"
        )
        self.sub = "http://cilogon.org/serverA/users/12345"
        SubAssociation.objects.create(sub=self.sub, profile=self.profile)
        self.return_to = "https://hcommons.org/broker-callback/"

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _login_with_userinfo(self):
        self.client.login(username="testuser", password="testpass")
        session = self.client.session
        session["oidc_userinfo"] = {
            "sub": self.sub,
            "email": "test@example.com",
            "name": "Test User",
            "idp_name": "Test University",
        }
        session.save()

    def test_authenticated_user_redirects_with_broker_token(self):
        self._login_with_userinfo()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("broker_token=", response.url)
        self.assertTrue(response.url.startswith("https://hcommons.org/"))

    def test_broker_token_nonce_is_verifiable(self):
        self._login_with_userinfo()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        # Extract broker_token and decrypt to get nonce
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]

        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)
        nonce = payload["nonce"]

        # Verify nonce via the verify endpoint
        verify_response = self.client.post(
            "/broker/verify-nonce/",
            data=json.dumps({"nonce": nonce}),
            content_type="application/json",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(verify_response.json()["valid"])

    def test_unauthenticated_redirects_with_no_session(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)
        self.assertTrue(response.url.startswith("https://hcommons.org/"))

    def test_missing_return_to_returns_400(self):
        response = self.client.get("/broker/silent-login/")
        self.assertEqual(response.status_code, 400)

    def test_invalid_return_to_returns_400(self):
        response = self.client.get(
            "/broker/silent-login/?return_to=https://evil.example.com/callback/"
        )
        self.assertEqual(response.status_code, 400)

    def test_authenticated_but_no_userinfo_redirects_no_session(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)

    def test_post_not_allowed(self):
        response = self.client.post(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 405)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestCilogonLoginBrokerFlow(CILogonTestBase):
    """Tests for the broker flow in cilogon_login()."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy"
    )
    @patch(
        "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri"
    )
    @patch("knowledge_commons_profiles.cilogon.views.oauth")
    def test_login_stores_return_to_in_session(
        self, mock_oauth, mock_redirect_uri, mock_state
    ):
        """Unauthenticated user with valid return_to gets it stored."""
        mock_oauth.cilogon.authorize_redirect.return_value = (
            HttpResponseRedirect("https://cilogon.org/authorize")
        )
        mock_redirect_uri.return_value = (
            "https://profile.hcommons.org/callback/"
        )
        mock_state.return_value = ""

        self.client.get(
            "/login/?return_to=https://hcommons.org/broker-callback/"
        )

        # Session should have broker_return_to stored
        self.assertEqual(
            self.client.session.get("broker_return_to"),
            "https://hcommons.org/broker-callback/",
        )

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy"
    )
    @patch(
        "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri"
    )
    @patch("knowledge_commons_profiles.cilogon.views.oauth")
    def test_login_ignores_invalid_return_to(
        self, mock_oauth, mock_redirect_uri, mock_state
    ):
        """Disallowed domain doesn't get stored."""
        mock_oauth.cilogon.authorize_redirect.return_value = (
            HttpResponseRedirect("https://cilogon.org/authorize")
        )
        mock_redirect_uri.return_value = (
            "https://profile.hcommons.org/callback/"
        )
        mock_state.return_value = ""

        self.client.get(
            "/login/?return_to=https://evil.example.com/callback/"
        )

        self.assertIsNone(self.client.session.get("broker_return_to"))

    @patch("knowledge_commons_profiles.cilogon.views.build_broker_redirect")
    @patch(
        "knowledge_commons_profiles.cilogon.views.SubAssociation"
    )
    def test_login_already_authenticated_redirects_immediately(
        self, mock_sub_class, mock_build_redirect
    ):
        """Authenticated user with valid return_to gets broker redirect."""
        # Create and log in a user
        User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client.login(username="testuser", password="testpass")

        # Set up session with userinfo
        session = self.client.session
        session["oidc_userinfo"] = {
            "sub": "http://cilogon.org/serverA/users/12345"
        }
        session.save()

        # Mock SubAssociation lookup
        mock_profile = MagicMock()
        mock_profile.username = "testuser"
        mock_sub = MagicMock()
        mock_sub.profile = mock_profile
        mock_sub_class.objects.filter.return_value.first.return_value = (
            mock_sub
        )

        mock_build_redirect.return_value = (
            "https://hcommons.org/broker-callback/?broker_token=encrypted"
        )

        response = self.client.get(
            "/login/?return_to=https://hcommons.org/broker-callback/"
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "https://hcommons.org/broker-callback/?broker_token=encrypted",
        )
        mock_build_redirect.assert_called_once()

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_forwarding_state_for_proxy"
    )
    @patch(
        "knowledge_commons_profiles.cilogon.views.get_oauth_redirect_uri"
    )
    @patch("knowledge_commons_profiles.cilogon.views.oauth")
    def test_login_already_authenticated_no_return_to(
        self, mock_oauth, mock_redirect_uri, mock_state
    ):
        """Authenticated user without return_to proceeds to normal flow."""
        User.objects.create_user(
            username="testuser2", password="testpass"
        )
        self.client.login(username="testuser2", password="testpass")

        mock_oauth.cilogon.authorize_redirect.return_value = (
            HttpResponseRedirect("https://cilogon.org/authorize")
        )
        mock_redirect_uri.return_value = (
            "https://profile.hcommons.org/callback/"
        )
        mock_state.return_value = ""

        # No return_to — should proceed to CILogon
        self.client.get("/login/")

        # Should have called authorize_redirect (normal flow)
        mock_oauth.cilogon.authorize_redirect.assert_called_once()


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestCallbackBrokerFlow(CILogonTestBase):
    """Tests for the broker flow in callback()."""

    @patch("knowledge_commons_profiles.cilogon.views.ExternalSync")
    @patch(
        "knowledge_commons_profiles.cilogon.views.find_user_and_login"
    )
    @patch(
        "knowledge_commons_profiles.cilogon.views.store_session_variables"
    )
    @patch("knowledge_commons_profiles.cilogon.views.forward_url")
    @patch("knowledge_commons_profiles.cilogon.views.oauth")
    @patch(
        "knowledge_commons_profiles.cilogon.views.build_broker_redirect"
    )
    def test_callback_redirects_with_broker_token(  # noqa: PLR0913
        self,
        mock_build_redirect,
        mock_oauth,
        mock_forward,
        mock_store,
        mock_find_login,
        mock_sync,
    ):
        """Successful login with broker_return_to redirects with token."""
        mock_forward.return_value = None

        userinfo = {
            "sub": "http://cilogon.org/serverA/users/12345",
            "email": "test@example.com",
            "idp_name": "Test University",
        }
        mock_oauth.cilogon.authorize_access_token.return_value = {
            "access_token": "test",
            "userinfo": userinfo,
        }
        mock_store.return_value = userinfo

        # Create profile and sub association
        profile = Profile.objects.create(
            username="testuser",
            email="test@example.com",
        )
        SubAssociation.objects.create(
            sub="http://cilogon.org/serverA/users/12345",
            profile=profile,
        )

        mock_build_redirect.return_value = (
            "https://hcommons.org/broker-callback/?broker_token=encrypted"
        )

        # Set broker_return_to in session
        session = self.client.session
        session["broker_return_to"] = (
            "https://hcommons.org/broker-callback/"
        )
        session.save()

        response = self.client.get("/cilogon/callback/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "https://hcommons.org/broker-callback/?broker_token=encrypted",
        )

    @patch("knowledge_commons_profiles.cilogon.views.ExternalSync")
    @patch(
        "knowledge_commons_profiles.cilogon.views.find_user_and_login"
    )
    @patch(
        "knowledge_commons_profiles.cilogon.views.store_session_variables"
    )
    @patch("knowledge_commons_profiles.cilogon.views.forward_url")
    @patch("knowledge_commons_profiles.cilogon.views.oauth")
    def test_callback_falls_back_to_profile(
        self,
        mock_oauth,
        mock_forward,
        mock_store,
        mock_find_login,
        mock_sync,
    ):
        """No broker_return_to redirects to profile (existing behavior)."""
        mock_forward.return_value = None

        userinfo = {
            "sub": "http://cilogon.org/serverA/users/99999",
            "email": "test2@example.com",
            "idp_name": "Test University",
        }
        mock_oauth.cilogon.authorize_access_token.return_value = {
            "access_token": "test",
            "userinfo": userinfo,
        }
        mock_store.return_value = userinfo

        profile = Profile.objects.create(
            username="testuser2",
            email="test2@example.com",
        )
        SubAssociation.objects.create(
            sub="http://cilogon.org/serverA/users/99999",
            profile=profile,
        )

        # No broker_return_to in session
        response = self.client.get("/cilogon/callback/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("my-profile", response.url)
