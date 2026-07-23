"""
Tests for the broker-client helpers used by satellite Profiles hosts.

A satellite host authenticates as a broker client of the hub: it builds
hub login / silent-login URLs pointing back at its own consumer, and it
verifies and one-time-consumes the broker tokens the hub returns.
"""

import time

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.cilogon import broker_client
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import _broker_encoder
from knowledge_commons_profiles.newprofile.models import Profile

CLIENT_HOST = "profile.stemedplus.org"


@override_settings(
    ALLOWED_HOSTS=["*"],
    BROKER_CLIENT_HOSTS=[CLIENT_HOST],
    CILOGON_REGISTERED_DOMAIN="profile.hcommons.org",
    STATIC_API_BEARER="test-bearer-key-for-broker-tokens",
    BROKER_NONCE_TTL=60,
)
class BrokerClientHelperTests(TestCase):
    def _request(self, host=CLIENT_HOST, path="/", **params):
        return RequestFactory().get(path, data=params, HTTP_HOST=host)

    def test_is_broker_client_host_true_for_configured_host(self):
        self.assertTrue(broker_client.is_broker_client_host(CLIENT_HOST))

    def test_is_broker_client_host_is_case_and_port_insensitive(self):
        self.assertTrue(
            broker_client.is_broker_client_host("PROFILE.STEMEDPLUS.ORG:443")
        )

    def test_is_broker_client_host_false_for_hub_and_others(self):
        self.assertFalse(
            broker_client.is_broker_client_host("profile.hcommons.org")
        )
        self.assertFalse(broker_client.is_broker_client_host("example.org"))

    def test_hub_login_url_targets_hub_with_consumer_return_to(self):
        url = broker_client.hub_login_url(
            self._request(), final_redirect="https://profile.stemedplus.org/x"
        )
        self.assertTrue(url.startswith("https://profile.hcommons.org/login/"))
        self.assertIn(
            "return_to=https%3A%2F%2Fprofile.stemedplus.org%2F", url
        )
        self.assertIn(
            "final_redirect=https%3A%2F%2Fprofile.stemedplus.org%2Fx", url
        )

    def test_hub_silent_login_url_targets_broker_silent_login(self):
        url = broker_client.hub_silent_login_url(self._request())
        self.assertTrue(
            url.startswith(
                "https://profile.hcommons.org/broker/silent-login/"
            )
        )
        self.assertIn("return_to=", url)

    def test_consumer_return_to_is_https_on_this_host(self):
        url = broker_client.consumer_return_to(self._request())
        self.assertTrue(url.startswith("https://profile.stemedplus.org/"))


def _make_token(sub="sub-123", exp_delta=60, nonce="nonce-abc",
                final_redirect="https://profile.stemedplus.org/after"):
    now = time.time()
    payload = {
        "userinfo": {"sub": sub, "email": "a@b.test", "name": "A B"},
        "kc_username": "alice",
        "primary_email": "a@b.test",
        "other_emails": [],
        "nonce": nonce,
        "iat": now,
        "exp": now + exp_delta,
        "final_redirect": final_redirect,
    }
    return _broker_encoder().encode(payload), payload


@override_settings(
    BROKER_CLIENT_HOSTS=[CLIENT_HOST],
    STATIC_API_BEARER="test-bearer-key-for-broker-tokens",
    BROKER_NONCE_TTL=60,
)
class ConsumeBrokerTokenTests(TestCase):
    def setUp(self):
        cache.clear()

    def _store_nonce(self, nonce, sub="sub-123"):
        cache.set(
            f"broker_nonce:{nonce}", {"used": False, "sub": sub}, timeout=60
        )

    def test_valid_token_returns_payload(self):
        token, payload = _make_token()
        self._store_nonce(payload["nonce"])
        result = broker_client.consume_broker_token(token)
        self.assertIsNotNone(result)
        self.assertEqual(result["userinfo"]["sub"], "sub-123")

    def test_valid_token_consumes_the_nonce(self):
        token, payload = _make_token()
        self._store_nonce(payload["nonce"])
        broker_client.consume_broker_token(token)
        self.assertIsNone(cache.get(f"broker_nonce:{payload['nonce']}"))

    def test_replayed_token_is_rejected(self):
        token, payload = _make_token()
        self._store_nonce(payload["nonce"])
        self.assertIsNotNone(broker_client.consume_broker_token(token))
        # nonce now consumed; a second use must fail
        self.assertIsNone(broker_client.consume_broker_token(token))

    def test_missing_nonce_is_rejected(self):
        token, _ = _make_token(nonce="never-stored")
        self.assertIsNone(broker_client.consume_broker_token(token))

    def test_expired_token_is_rejected(self):
        token, payload = _make_token(exp_delta=-1)
        self._store_nonce(payload["nonce"])
        self.assertIsNone(broker_client.consume_broker_token(token))

    def test_garbage_token_is_rejected(self):
        self.assertIsNone(broker_client.consume_broker_token("not-a-token"))

    def test_empty_token_is_rejected(self):
        self.assertIsNone(broker_client.consume_broker_token(""))


@override_settings(
    ALLOWED_HOSTS=["*"],
    BROKER_CLIENT_HOSTS=[CLIENT_HOST],
    CILOGON_REGISTERED_DOMAIN="profile.hcommons.org",
    STATIC_API_BEARER="test-bearer-key-for-broker-tokens",
    BROKER_NONCE_TTL=60,
    BROKER_CLIENT_SSO_COOKIE="kc_sso_checked",
    BROKER_CLIENT_SILENT_LOGIN_TTL=300,
)
class BrokerClientLoginViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.profile = Profile.objects.create(
            username="alice", name="Alice", email="a@b.test"
        )
        self.sub = "sub-123"
        SubAssociation.objects.create(sub=self.sub, profile=self.profile)

    def _store_nonce(self, nonce):
        cache.set(
            f"broker_nonce:{nonce}",
            {"used": False, "sub": self.sub},
            timeout=60,
        )

    def test_valid_token_logs_the_user_in_locally(self):
        token, payload = _make_token(sub=self.sub, final_redirect="")
        self._store_nonce(payload["nonce"])
        response = self.client.get(
            reverse("broker_client_login"),
            data={"broker_token": token},
            headers={"host": CLIENT_HOST}
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="alice")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_valid_token_sets_the_sso_marker_cookie(self):
        token, payload = _make_token(sub=self.sub, final_redirect="")
        self._store_nonce(payload["nonce"])
        response = self.client.get(
            reverse("broker_client_login"),
            data={"broker_token": token},
            headers={"host": CLIENT_HOST}
        )
        self.assertIn("kc_sso_checked", response.cookies)

    def test_no_token_proceeds_anonymously_and_sets_marker(self):
        response = self.client.get(
            reverse("broker_client_login"), headers={"host": CLIENT_HOST}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertIn("kc_sso_checked", response.cookies)

    def test_safe_final_redirect_from_token_is_honoured(self):
        # on a successful login the onward page rides inside the token,
        # not as a query param
        token, payload = _make_token(
            sub=self.sub,
            final_redirect=f"https://{CLIENT_HOST}/members/alice/",
        )
        self._store_nonce(payload["nonce"])
        response = self.client.get(
            reverse("broker_client_login"),
            data={"broker_token": token},
            headers={"host": CLIENT_HOST},
        )
        self.assertEqual(
            response["Location"], f"https://{CLIENT_HOST}/members/alice/"
        )

    def test_no_session_final_redirect_from_query_is_honoured(self):
        # the no-session case (no token) carries the onward page as a query
        # param
        response = self.client.get(
            reverse("broker_client_login"),
            data={
                "no_session": "1",
                "final_redirect": f"https://{CLIENT_HOST}/members/",
            },
            headers={"host": CLIENT_HOST},
        )
        self.assertEqual(
            response["Location"], f"https://{CLIENT_HOST}/members/"
        )

    def test_offsite_final_redirect_is_rejected(self):
        response = self.client.get(
            reverse("broker_client_login"),
            data={"final_redirect": "https://evil.example/steal"},
            headers={"host": CLIENT_HOST}
        )
        self.assertNotIn("evil.example", response["Location"])

    def test_offsite_final_redirect_in_token_is_rejected(self):
        token, payload = _make_token(
            sub=self.sub, final_redirect="https://evil.example/steal"
        )
        self._store_nonce(payload["nonce"])
        response = self.client.get(
            reverse("broker_client_login"),
            data={"broker_token": token},
            headers={"host": CLIENT_HOST},
        )
        self.assertNotIn("evil.example", response["Location"])

    def test_consumer_is_404_on_non_client_host(self):
        response = self.client.get(
            reverse("broker_client_login"),
            headers={"host": "profile.hcommons.org"},
        )
        self.assertEqual(response.status_code, 404)


@override_settings(
    ALLOWED_HOSTS=["*"],
    BROKER_CLIENT_HOSTS=[CLIENT_HOST],
    CILOGON_REGISTERED_DOMAIN="profile.hcommons.org",
)
class SatelliteLoginDelegationTests(TestCase):
    def test_login_on_client_host_delegates_to_hub(self):
        response = self.client.get(
            reverse("login"),
            data={"next": "/members/"},
            headers={"host": CLIENT_HOST},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith(
                "https://profile.hcommons.org/login/"
            )
        )
        self.assertIn(
            "final_redirect=https%3A%2F%2Fprofile.stemedplus.org%2Fmembers%2F",
            response["Location"],
        )
