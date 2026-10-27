"""
The production sync engine must reach UP Salesforce through the External
Client App credentials, not the legacy refresh-token flow.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

ECA_QUERY_URL = f"{INSTANCE_URL}/services/data/v62.0/query"
LEGACY_BASE = "https://legacy.example.my.salesforce.com/services/data/v39.0/"


@override_settings(
    UP_ECA_CONSUMER_KEY="consumer-key",
    UP_ECA_CONSUMER_SECRET="consumer-secret",
    UP_ECA_LOGIN_URL="https://example.my.salesforce.com",
    UP_ECA_API_VERSION="v62.0",
    UP_API_BASE_URL=LEGACY_BASE,
    UP_API_TOKEN="legacy-token",
    UP_REFRESH_TOKEN="legacy-refresh",
)
class ProductionUPSyncWiringTests(TestCase):
    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))
        self.session.add(
            "GET",
            ECA_QUERY_URL,
            FakeResponse(
                200,
                {
                    "totalSize": 1,
                    "done": True,
                    "records": [
                        {
                            "attributes": {"type": "Contact", "url": "/x"},
                            "Id": "003xx",
                            "Name": "Ada",
                            "Email": "ada@example.org",
                            "AccountId": "001xx",
                            "Current_Staff__c": True,
                            "UP_Commons_Eligible__c": True,
                        }
                    ],
                },
            ),
        )
        # Any request to the legacy base URL would hit an unrouted URL in
        # the fake session and fail loudly.
        for target, side_effect in (
            ("requests.Session.request", self.session.request),
            (
                "requests.post",
                lambda url, **kw: self.session.request("POST", url, **kw),
            ),
        ):
            patcher = mock.patch(target, side_effect=side_effect)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.profile = Profile.objects.create(
            username="ada", email="ada@example.org", emails=[]
        )

    def test_up_sync_uses_external_client_app_credentials(self):
        result = ExternalSync.sync(
            self.profile,
            class_list=[("UP", ["Association of American University Presses"])],
            send_webhook=False,
            cache=False,
            webhooks=False,
        )

        self.assertTrue(result["UP"])
        token_calls = self.session.calls_to(TOKEN_URL)
        self.assertEqual(len(token_calls), 1)
        self.assertEqual(
            token_calls[0]["data"]["grant_type"], "client_credentials"
        )
        self.assertEqual(len(self.session.calls_to(ECA_QUERY_URL)), 1)
        self.assertFalse(
            [c for c in self.session.calls if c["url"].startswith(LEGACY_BASE)]
        )
