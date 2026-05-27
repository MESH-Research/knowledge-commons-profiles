"""
Tests for the broker Referer gate.

The browser-facing broker endpoints (currently /broker/silent-login/) must
only honour requests originating from a configured allowlist of domains.
The server-to-server /broker/verify-nonce/ endpoint must NOT be gated by
Referer — it already requires a Bearer token.
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.broker_referer import referer_is_allowed
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.newprofile.models import Profile

BROKER_SETTINGS = {
    "wordpress": {
        "name": "WordPress",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "msu.edu", "localhost"],
    },
    "works": {
        "name": "Works",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "msu.edu", "localhost"],
    },
}

TEST_SHARED_SECRET = "test-shared-secret-for-broker"


@override_settings(
    BROKER_ALLOWED_REFERER_DOMAINS=["hcommons.org", "msu.edu"],
)
class TestRefererIsAllowed(TestCase):
    """Unit tests for the referer_is_allowed helper."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def test_bare_allowed_domain_accepted(self):
        request = self.factory.get(
            "/broker/silent-login/", HTTP_REFERER="https://hcommons.org/"
        )
        self.assertTrue(referer_is_allowed(request))

    def test_subdomain_of_allowed_domain_accepted(self):
        request = self.factory.get(
            "/broker/silent-login/",
            HTTP_REFERER="https://works.hcommons.org/some/page",
        )
        self.assertTrue(referer_is_allowed(request))

    def test_msu_subdomain_accepted(self):
        request = self.factory.get(
            "/broker/silent-login/",
            HTTP_REFERER="https://commons.msu.edu/whatever",
        )
        self.assertTrue(referer_is_allowed(request))

    def test_unrelated_domain_rejected(self):
        request = self.factory.get(
            "/broker/silent-login/",
            HTTP_REFERER="https://evil.example.com/",
        )
        self.assertFalse(referer_is_allowed(request))

    def test_suffix_lookalike_rejected(self):
        """`evilhcommons.org` must not match `hcommons.org` as a suffix."""
        request = self.factory.get(
            "/broker/silent-login/",
            HTTP_REFERER="https://evilhcommons.org/",
        )
        self.assertFalse(referer_is_allowed(request))

    def test_missing_referer_rejected(self):
        request = self.factory.get("/broker/silent-login/")
        self.assertFalse(referer_is_allowed(request))

    def test_empty_referer_rejected(self):
        request = self.factory.get(
            "/broker/silent-login/", HTTP_REFERER=""
        )
        self.assertFalse(referer_is_allowed(request))

    def test_malformed_referer_rejected(self):
        request = self.factory.get(
            "/broker/silent-login/", HTTP_REFERER="not a url"
        )
        self.assertFalse(referer_is_allowed(request))

    def test_setting_is_honoured(self):
        """A domain only allowed by override_settings should be accepted."""
        with override_settings(
            BROKER_ALLOWED_REFERER_DOMAINS=["example.org"]
        ):
            request = self.factory.get(
                "/broker/silent-login/",
                HTTP_REFERER="https://sub.example.org/",
            )
            self.assertTrue(referer_is_allowed(request))

            request2 = self.factory.get(
                "/broker/silent-login/",
                HTTP_REFERER="https://hcommons.org/",
            )
            self.assertFalse(referer_is_allowed(request2))

    def test_case_insensitive_host_match(self):
        request = self.factory.get(
            "/broker/silent-login/",
            HTTP_REFERER="https://WORKS.HCOMMONS.ORG/page",
        )
        self.assertTrue(referer_is_allowed(request))


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
    BROKER_ALLOWED_REFERER_DOMAINS=["hcommons.org", "msu.edu"],
)
class TestSilentLoginRefererGate(TestCase):
    """Integration tests: /broker/silent-login/ enforces the Referer gate."""

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

    def test_missing_referer_returns_403(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 403)

    def test_disallowed_referer_returns_403(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}",
            headers={"referer": "https://evil.example.com/"}
        )
        self.assertEqual(response.status_code, 403)

    def test_allowed_bare_domain_referer_passes_gate(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}",
            headers={"referer": "https://hcommons.org/some/page"}
        )
        # Gate passed; user is unauthenticated so we get the no_session
        # redirect (302), not a 403.
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)

    def test_allowed_subdomain_referer_passes_gate(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}",
            headers={"referer": "https://works.hcommons.org/some/page"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)

    def test_msu_subdomain_referer_passes_gate(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}",
            headers={"referer": "https://commons.msu.edu/page"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("no_session=1", response.url)

    def test_gate_is_configurable(self):
        """With env-overridden domain list, only the new list is allowed."""
        with override_settings(
            BROKER_ALLOWED_REFERER_DOMAINS=["example.org"]
        ):
            # hcommons.org no longer allowed under this override
            blocked = self.client.get(
                f"/broker/silent-login/?return_to={self.return_to}",
                headers={"referer": "https://hcommons.org/page"}
            )
            self.assertEqual(blocked.status_code, 403)

            # example.org now allowed
            allowed = self.client.get(
                f"/broker/silent-login/?return_to={self.return_to}",
                headers={"referer": "https://example.org/page"}
            )
            self.assertEqual(allowed.status_code, 302)

    def test_verify_nonce_not_gated_by_referer(self):
        """verify-nonce is server-to-server; must not require a Referer."""
        # Seed a nonce in cache so the endpoint has something to consume.
        with patch(
            "knowledge_commons_profiles.cilogon.views.cache"
        ) as mock_cache:
            mock_cache.get.return_value = {"sub": self.sub}
            response = self.client.post(
                "/broker/verify-nonce/",
                data=json.dumps({"nonce": "abc"}),
                content_type="application/json",
                headers={
                    "authorization": f"Bearer {TEST_SHARED_SECRET}"
                },
                # Deliberately no HTTP_REFERER
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
