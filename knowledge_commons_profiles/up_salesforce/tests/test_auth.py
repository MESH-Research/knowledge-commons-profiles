from django.core.cache import cache
from django.test import SimpleTestCase
from django.test import override_settings

from knowledge_commons_profiles.up_salesforce.auth import (
    ClientCredentialsTokenProvider,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceAuthError,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceConfigurationError,
)
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

SETTINGS = {
    "UP_ECA_CONSUMER_KEY": "consumer-key",
    "UP_ECA_CONSUMER_SECRET": "consumer-secret",
    "UP_ECA_LOGIN_URL": "https://example.my.salesforce.com",
    "UP_ECA_TOKEN_CACHE_TIMEOUT": 600,
}


@override_settings(**SETTINGS)
class ClientCredentialsTokenProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))

    def provider(self, **kwargs):
        return ClientCredentialsTokenProvider(session=self.session, **kwargs)

    def test_token_url_is_derived_from_login_url(self):
        self.assertEqual(self.provider().token_url, TOKEN_URL)

    def test_token_url_tolerates_trailing_slash(self):
        provider = self.provider(login_url="https://example.my.salesforce.com/")
        self.assertEqual(provider.token_url, TOKEN_URL)

    def test_fetch_token_returns_parsed_token(self):
        token = self.provider().fetch_token()
        self.assertEqual(token.access_token, TOKEN_BODY["access_token"])
        self.assertEqual(token.instance_url, INSTANCE_URL)

    def test_fetch_token_uses_client_credentials_grant(self):
        self.provider().fetch_token()
        call = self.session.calls_to(TOKEN_URL)[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["data"]["grant_type"], "client_credentials")
        self.assertEqual(call["data"]["client_id"], "consumer-key")
        self.assertEqual(call["data"]["client_secret"], "consumer-secret")

    def test_explicit_credentials_override_settings(self):
        self.provider(
            consumer_key="other-key", consumer_secret="other-secret"
        ).fetch_token()
        call = self.session.calls_to(TOKEN_URL)[0]
        self.assertEqual(call["data"]["client_id"], "other-key")
        self.assertEqual(call["data"]["client_secret"], "other-secret")

    @override_settings(UP_ECA_CONSUMER_KEY="", UP_ECA_CONSUMER_SECRET="")
    def test_missing_credentials_raise_configuration_error(self):
        with self.assertRaises(UPSalesforceConfigurationError):
            self.provider().fetch_token()
        self.assertEqual(self.session.calls, [])

    def test_salesforce_error_response_raises_auth_error_with_reason(self):
        self.session.add(
            "POST",
            TOKEN_URL,
            FakeResponse(
                400,
                {
                    "error": "invalid_client",
                    "error_description": "invalid client credentials",
                },
            ),
        )
        with self.assertRaises(UPSalesforceAuthError) as ctx:
            self.provider().fetch_token()
        self.assertIn("invalid_client", str(ctx.exception))
        self.assertIn("invalid client credentials", str(ctx.exception))

    def test_non_json_error_response_still_raises_auth_error(self):
        self.session.add(
            "POST", TOKEN_URL, FakeResponse(503, None, text="Service down")
        )
        with self.assertRaises(UPSalesforceAuthError):
            self.provider().fetch_token()

    def test_malformed_success_body_raises_auth_error(self):
        self.session.add("POST", TOKEN_URL, FakeResponse(200, {"nope": 1}))
        with self.assertRaises(UPSalesforceAuthError):
            self.provider().fetch_token()

    def test_get_token_caches_between_calls(self):
        provider = self.provider()
        first = provider.get_token()
        second = provider.get_token()
        self.assertEqual(first.access_token, second.access_token)
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)

    def test_cache_is_shared_between_provider_instances(self):
        self.provider().get_token()
        self.provider().get_token()
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)

    def test_peek_cached_does_not_contact_salesforce(self):
        provider = self.provider()
        self.assertIsNone(provider.peek_cached())
        provider.get_token()
        self.assertEqual(
            provider.peek_cached().access_token, TOKEN_BODY["access_token"]
        )
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)

    def test_force_refresh_fetches_a_new_token(self):
        provider = self.provider()
        provider.get_token()
        self.session.add(
            "POST",
            TOKEN_URL,
            FakeResponse(
                200, {**TOKEN_BODY, "access_token": "new-token-value"}
            ),
        )
        token = provider.get_token(force_refresh=True)
        self.assertEqual(token.access_token, "new-token-value")
        self.assertEqual(provider.peek_cached().access_token, "new-token-value")

    def test_invalidate_clears_cache(self):
        provider = self.provider()
        provider.get_token()
        provider.invalidate()
        self.assertIsNone(provider.peek_cached())
        provider.get_token()
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 2)


class LazySettingsTests(SimpleTestCase):
    """
    A provider built at import time (as the production sync registry does)
    must honour settings as they are when it is used, not when it was
    constructed; explicit constructor values still win.
    """

    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))

    @override_settings(
        UP_ECA_CONSUMER_KEY="", UP_ECA_CONSUMER_SECRET="", UP_ECA_LOGIN_URL=""
    )
    def test_settings_applied_after_construction_are_used(self):
        provider = ClientCredentialsTokenProvider(session=self.session)
        with override_settings(**SETTINGS):
            token = provider.fetch_token()
        self.assertEqual(token.access_token, TOKEN_BODY["access_token"])
        call = self.session.calls_to(TOKEN_URL)[0]
        self.assertEqual(call["data"]["client_id"], "consumer-key")
        self.assertEqual(call["data"]["client_secret"], "consumer-secret")

    @override_settings(**SETTINGS)
    def test_explicit_constructor_values_are_not_overridden_by_settings(self):
        provider = ClientCredentialsTokenProvider(
            session=self.session, consumer_key="explicit-key"
        )
        with override_settings(UP_ECA_CONSUMER_KEY="later-key"):
            provider.fetch_token()
        call = self.session.calls_to(TOKEN_URL)[0]
        self.assertEqual(call["data"]["client_id"], "explicit-key")

    @override_settings(**SETTINGS)
    def test_login_url_changes_are_honoured(self):
        provider = ClientCredentialsTokenProvider(session=self.session)
        with override_settings(UP_ECA_LOGIN_URL="https://other.example"):
            self.assertEqual(
                provider.token_url,
                "https://other.example/services/oauth2/token",
            )
