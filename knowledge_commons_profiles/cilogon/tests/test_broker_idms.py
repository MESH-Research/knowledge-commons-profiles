"""
Tests for the asynchronous IDMS broker views and their URLconf.

These exercise ``knowledge_commons_profiles.cilogon.broker_views`` served via
``config.broker_urls`` (the minimal URLconf the standalone IDMS ASGI container
uses). Behaviour must match the synchronous broker views in ``cilogon.views``
served by the main app — so the assertions deliberately mirror
``test_broker.py`` — while additionally covering routing isolation, the health
probe, and execution under a real event loop (``AsyncClient``) to catch
``SynchronousOnlyOperation`` regressions that the sync test client would mask.
"""

import json
from unittest.mock import AsyncMock
from unittest.mock import patch
from urllib.parse import parse_qs
from urllib.parse import urlparse

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import SecureParamEncoder
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

BROKER_OVERRIDES = {
    "ROOT_URLCONF": "config.broker_urls",
    "BROKER_REGISTERED_APPS": BROKER_SETTINGS,
    "BROKER_NONCE_TTL": 60,
    "STATIC_API_BEARER": TEST_SHARED_SECRET,
}


@override_settings(**BROKER_OVERRIDES)
class TestBrokerSilentLoginAsync(TestCase):
    """Behaviour of the async silent_login view via config.broker_urls."""

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
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]

        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)
        nonce = payload["nonce"]

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

    def test_missing_return_to_redirects_to_fallback(self):
        with override_settings(
            BROKER_FALLBACK_REDIRECT_URL="https://hcommons.org/"
        ):
            response = self.client.get("/broker/silent-login/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://hcommons.org/")

    def test_invalid_return_to_redirects_to_fallback(self):
        with override_settings(
            BROKER_FALLBACK_REDIRECT_URL="https://hcommons.org/"
        ):
            response = self.client.get(
                "/broker/silent-login/"
                "?return_to=https://evil.example.com/callback/",
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://hcommons.org/")

    def test_authenticated_but_no_userinfo_redirects_no_session(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)

    def test_no_session_includes_final_redirect(self):
        final = "https://hcommons.org/some-article/"
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
            f"&final_redirect={final}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        self.assertEqual(params["final_redirect"][0], final)

    def test_final_redirect_in_broker_token(self):
        self._login_with_userinfo()
        final = "https://hcommons.org/some-article/"
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
            f"&final_redirect={final}"
        )
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        token = params["broker_token"][0]
        encoder = SecureParamEncoder(TEST_SHARED_SECRET)
        payload = encoder.decode(token)
        self.assertEqual(payload["final_redirect"], final)

    def test_post_not_allowed(self):
        response = self.client.post(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 405)

    def test_authenticated_response_is_uncacheable(self):
        self._login_with_userinfo()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_unauthenticated_response_is_uncacheable(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Cache-Control"], "no-store")


@override_settings(**BROKER_OVERRIDES)
class TestBrokerVerifyNonceAsync(TestCase):
    """Async verify_broker_nonce behaviour via config.broker_urls."""

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
            headers={"authorization": f"Bearer {bearer}"},
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
        self.assertEqual(data["sub"], "http://cilogon.org/serverA/users/12345")

    def test_nonce_consumed_after_verification(self):
        cache.set(
            "broker_nonce:test-nonce-456",
            {"used": False, "sub": "http://cilogon.org/serverA/users/12345"},
            timeout=60,
        )
        response = self._make_request("test-nonce-456")
        self.assertEqual(response.status_code, 200)
        # Replay must be rejected.
        response = self._make_request("test-nonce-456")
        self.assertEqual(response.status_code, 410)

    def test_expired_nonce_returns_410(self):
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
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_body_returns_400(self):
        response = self.client.post(
            "/broker/verify-nonce/",
            data="not-json",
            content_type="application/json",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertEqual(response.status_code, 400)

    def test_csrf_exempt_no_403(self):
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
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertEqual(response.status_code, 405)


@override_settings(**BROKER_OVERRIDES)
class TestBrokerUrlsIsolation(TestCase):
    """The IDMS URLconf serves only broker routes; everything else 404s."""

    def test_broker_silent_login_resolves(self):
        # A bad return_to still resolves the route (302 to fallback), proving
        # the path is served rather than 404.
        with override_settings(
            BROKER_FALLBACK_REDIRECT_URL="https://hcommons.org/"
        ):
            response = self.client.get("/broker/silent-login/")
        self.assertEqual(response.status_code, 302)

    def test_non_broker_path_returns_404(self):
        # Routes that live in the main app's URLconf must NOT be served here.
        response = self.client.get("/members/someone/settings/")
        self.assertEqual(response.status_code, 404)

    def test_login_path_returns_404(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 404)


@override_settings(**BROKER_OVERRIDES)
class TestBrokerHealth(TestCase):
    """The async health probe reports backend reachability."""

    def test_health_ok_returns_200(self):
        response = self.client.get("/broker/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_failure_returns_500(self):
        with patch(
            "knowledge_commons_profiles.cilogon.broker_views.cache"
        ) as mock_cache:
            mock_cache.aget = AsyncMock(side_effect=Exception("redis down"))
            response = self.client.get("/broker/health/")
        self.assertEqual(response.status_code, 500)


@override_settings(**BROKER_OVERRIDES)
class TestBrokerSilentLoginRealEventLoop(TestCase):
    """Exercise the async views under a real event loop via AsyncClient.

    The synchronous test client runs async views through ``async_to_sync``,
    which permits synchronous ORM access and so masks
    ``SynchronousOnlyOperation`` bugs. These tests drive the views on a real
    event loop, the way uvicorn will in production.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(
            username="asyncuser", password="testpass"
        )
        self.profile = Profile.objects.create(
            username="asyncuser", email="async@example.com"
        )
        self.sub = "http://cilogon.org/serverA/users/99999"
        SubAssociation.objects.create(sub=self.sub, profile=self.profile)
        self.return_to = "https://hcommons.org/broker-callback/"

    def tearDown(self):
        cache.clear()
        super().tearDown()

    async def test_unauthenticated_no_session_real_loop(self):
        response = await self.async_client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response["Location"])

    async def test_authenticated_broker_token_real_loop(self):
        await self.async_client.aforce_login(self.user)
        session = self.async_client.session
        session["oidc_userinfo"] = {
            "sub": self.sub,
            "email": "async@example.com",
            "name": "Async User",
            "idp_name": "Test University",
        }
        await sync_to_async(session.save)()
        response = await self.async_client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("broker_token=", response["Location"])
