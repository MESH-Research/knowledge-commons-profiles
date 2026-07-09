"""
Tests that the silent-SSO broker degrades gracefully in maintenance mode.

The whole point of maintenance mode for the broker is that dependent apps
(WordPress, Works) must NOT crash: instead of an error, the broker returns the
existing "not logged in" contract (a 302 back to return_to carrying
``no_session=1``) without minting a token or touching session state — even for
a user who actually has a live session.
"""

from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.cilogon.models import SubAssociation
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

FALLBACK_URL = "https://hcommons.org"

# Match the shared secret used across the other broker tests: the broker
# encoder is a module-level singleton keyed on STATIC_API_BEARER the first
# time it is built, so every broker-exercising test must agree on the secret.
TEST_SHARED_SECRET = "test-shared-secret-for-broker"


def _enable_maintenance():
    obj = MaintenanceMode.load()
    obj.enabled = True
    obj.save()


class _BrokerMaintenanceBase(TestCase):
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


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_FALLBACK_REDIRECT_URL=FALLBACK_URL,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestSyncBrokerMaintenance(_BrokerMaintenanceBase):
    """The synchronous silent_login served by the main app."""

    def test_authenticated_user_gets_no_session_in_maintenance(self):
        self._login_with_userinfo()
        _enable_maintenance()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlparse(response.url).query)
        self.assertEqual(params.get("no_session"), ["1"])
        self.assertNotIn("broker_token", params)

    def test_no_session_carries_final_redirect_in_maintenance(self):
        self._login_with_userinfo()
        _enable_maintenance()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
            "&final_redirect=https://hcommons.org/dashboard/"
        )
        params = parse_qs(urlparse(response.url).query)
        self.assertEqual(params.get("no_session"), ["1"])
        self.assertEqual(
            params.get("final_redirect"),
            ["https://hcommons.org/dashboard/"],
        )

    def test_invalid_return_to_still_falls_back_in_maintenance(self):
        _enable_maintenance()
        response = self.client.get(
            "/broker/silent-login/?return_to=https://evil.example.com/cb/"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, FALLBACK_URL)

    def test_normal_token_flow_when_not_in_maintenance(self):
        self._login_with_userinfo()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("broker_token=", response.url)


@override_settings(
    ROOT_URLCONF="config.broker_urls",
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_FALLBACK_REDIRECT_URL=FALLBACK_URL,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class TestAsyncBrokerMaintenance(_BrokerMaintenanceBase):
    """The asynchronous silent_login served by the IDMS container."""

    def test_authenticated_user_gets_no_session_in_maintenance(self):
        self._login_with_userinfo()
        _enable_maintenance()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlparse(response.url).query)
        self.assertEqual(params.get("no_session"), ["1"])
        self.assertNotIn("broker_token", params)

    def test_invalid_return_to_still_falls_back_in_maintenance(self):
        _enable_maintenance()
        response = self.client.get(
            "/broker/silent-login/?return_to=https://evil.example.com/cb/"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, FALLBACK_URL)

    def test_normal_token_flow_when_not_in_maintenance(self):
        self._login_with_userinfo()
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("broker_token=", response.url)
