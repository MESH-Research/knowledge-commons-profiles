from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase
from django.test import override_settings

from knowledge_commons_profiles.up_salesforce.auth import (
    ClientCredentialsTokenProvider,
)
from knowledge_commons_profiles.up_salesforce.client import SalesforceRestClient
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceAuthError,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceError,
)
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

DATA = f"{INSTANCE_URL}/services/data/v62.0"
QUERY_URL = f"{DATA}/query"
QUERY_RESULT = {
    "totalSize": 1,
    "done": True,
    "records": [{"Id": "003xx", "Name": "Ada"}],
}


@override_settings(
    UP_ECA_CONSUMER_KEY="consumer-key",
    UP_ECA_CONSUMER_SECRET="consumer-secret",
    UP_ECA_LOGIN_URL="https://example.my.salesforce.com",
    UP_ECA_API_VERSION="v62.0",
)
class SalesforceRestClientTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))
        self.provider = ClientCredentialsTokenProvider(session=self.session)
        self.client = SalesforceRestClient(
            token_provider=self.provider, session=self.session
        )

    def test_build_url_relative_path_uses_versioned_data_root(self):
        self.assertEqual(
            self.client.build_url("query", INSTANCE_URL), QUERY_URL
        )

    def test_build_url_absolute_path_is_appended_to_instance(self):
        self.assertEqual(
            self.client.build_url("/services/oauth2/userinfo", INSTANCE_URL),
            f"{INSTANCE_URL}/services/oauth2/userinfo",
        )

    def test_build_url_full_url_is_untouched(self):
        self.assertEqual(
            self.client.build_url("https://other/x", INSTANCE_URL),
            "https://other/x",
        )

    def test_api_version_can_be_overridden(self):
        client = SalesforceRestClient(
            token_provider=self.provider,
            session=self.session,
            api_version="v58.0",
        )
        self.assertEqual(
            client.build_url("limits", INSTANCE_URL),
            f"{INSTANCE_URL}/services/data/v58.0/limits",
        )

    def test_request_sends_bearer_token_and_returns_json(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, QUERY_RESULT))
        result = self.client.request("GET", "query", params={"q": "SELECT"})
        self.assertEqual(result, QUERY_RESULT)
        call = self.session.calls_to(QUERY_URL)[0]
        self.assertEqual(
            call["headers"]["Authorization"],
            f"Bearer {TOKEN_BODY['access_token']}",
        )
        self.assertEqual(call["params"], {"q": "SELECT"})

    def test_request_reuses_cached_token(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, QUERY_RESULT))
        self.client.request("GET", "query")
        self.client.request("GET", "query")
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)

    def test_401_refreshes_token_and_retries_once(self):
        self.session.add(
            "POST",
            TOKEN_URL,
            FakeResponse(200, TOKEN_BODY),
            FakeResponse(200, {**TOKEN_BODY, "access_token": "fresh-token"}),
        )
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                401,
                [{"errorCode": "INVALID_SESSION_ID", "message": "expired"}],
            ),
            FakeResponse(200, QUERY_RESULT),
        )
        result = self.client.request("GET", "query")
        self.assertEqual(result, QUERY_RESULT)
        calls = self.session.calls_to(QUERY_URL)
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[1]["headers"]["Authorization"], "Bearer fresh-token"
        )

    def test_persistent_401_raises_auth_error(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                401,
                [{"errorCode": "INVALID_SESSION_ID", "message": "expired"}],
            ),
        )
        with self.assertRaises(UPSalesforceAuthError):
            self.client.request("GET", "query")
        self.assertEqual(len(self.session.calls_to(QUERY_URL)), 2)

    def test_salesforce_error_payload_is_surfaced(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                400,
                [
                    {
                        "errorCode": "MALFORMED_QUERY",
                        "message": "unexpected token: FORM",
                    }
                ],
            ),
        )
        with self.assertRaises(UPSalesforceError) as ctx:
            self.client.request("GET", "query")
        self.assertIn("MALFORMED_QUERY", str(ctx.exception))
        self.assertIn("unexpected token", str(ctx.exception))

    def test_non_json_error_still_raises(self):
        self.session.add(
            "GET", QUERY_URL, FakeResponse(502, None, text="Bad gateway")
        )
        with self.assertRaises(UPSalesforceError):
            self.client.request("GET", "query")

    def test_empty_body_returns_none(self):
        url = f"{DATA}/sobjects/Contact/003xx"
        self.session.add("DELETE", url, FakeResponse(204, None, text=""))
        self.assertIsNone(
            self.client.request("DELETE", "sobjects/Contact/003xx")
        )

    def test_query_passes_soql_as_q_parameter(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, QUERY_RESULT))
        result = self.client.query("SELECT Id FROM Contact")
        self.assertEqual(result, QUERY_RESULT)
        call = self.session.calls_to(QUERY_URL)[0]
        self.assertEqual(call["params"], {"q": "SELECT Id FROM Contact"})

    def test_query_all_follows_next_records_url(self):
        next_path = "/services/data/v62.0/query/01gxx-2000"
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200,
                {
                    "totalSize": 3,
                    "done": False,
                    "nextRecordsUrl": next_path,
                    "records": [{"Id": "1"}, {"Id": "2"}],
                },
            ),
        )
        self.session.add(
            "GET",
            f"{INSTANCE_URL}{next_path}",
            FakeResponse(
                200, {"totalSize": 3, "done": True, "records": [{"Id": "3"}]}
            ),
        )
        records = self.client.query_all("SELECT Id FROM Contact")
        self.assertEqual([r["Id"] for r in records], ["1", "2", "3"])

    def test_limits(self):
        payload = {"DailyApiRequests": {"Max": 15000, "Remaining": 14990}}
        self.session.add("GET", f"{DATA}/limits", FakeResponse(200, payload))
        self.assertEqual(self.client.limits(), payload)

    def test_userinfo_uses_oauth_endpoint_on_instance(self):
        payload = {"user_id": "005xx", "preferred_username": "api@example"}
        self.session.add(
            "GET",
            f"{INSTANCE_URL}/services/oauth2/userinfo",
            FakeResponse(200, payload),
        )
        self.assertEqual(self.client.userinfo(), payload)

    def test_versions(self):
        payload = [
            {
                "label": "Winter '25",
                "url": "/services/data/v62.0",
                "version": "62.0",
            }
        ]
        self.session.add(
            "GET", f"{INSTANCE_URL}/services/data/", FakeResponse(200, payload)
        )
        self.assertEqual(self.client.versions(), payload)

    def test_describe(self):
        payload = {"name": "Contact", "fields": []}
        self.session.add(
            "GET",
            f"{DATA}/sobjects/Contact/describe",
            FakeResponse(200, payload),
        )
        self.assertEqual(self.client.describe("Contact"), payload)


class ClientLazySettingsTests(SimpleTestCase):
    @override_settings(UP_ECA_API_VERSION="v58.0")
    def test_api_version_is_read_when_used_not_when_constructed(self):
        client = SalesforceRestClient(
            token_provider=mock.Mock(), session=FakeSession()
        )
        with override_settings(UP_ECA_API_VERSION="v62.0"):
            self.assertEqual(
                client.build_url("limits", INSTANCE_URL),
                f"{INSTANCE_URL}/services/data/v62.0/limits",
            )

    def test_explicit_api_version_wins_over_settings(self):
        client = SalesforceRestClient(
            token_provider=mock.Mock(),
            session=FakeSession(),
            api_version="v58.0",
        )
        with override_settings(UP_ECA_API_VERSION="v62.0"):
            self.assertEqual(
                client.build_url("limits", INSTANCE_URL),
                f"{INSTANCE_URL}/services/data/v58.0/limits",
            )
