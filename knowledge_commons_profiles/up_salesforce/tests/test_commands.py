"""
Management command tests. The network boundary (``requests.Session``) is
replaced with an in-memory fake so the commands exercise the real token
provider, client and sync code without touching Salesforce.
"""

import json
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

DATA = f"{INSTANCE_URL}/services/data/v62.0"
QUERY_URL = f"{DATA}/query"
CONTACT = {
    "attributes": {"type": "Contact", "url": "/x"},
    "Id": "003xx",
    "Name": "Ada Lovelace",
    "Email": "ada@example.org",
    "AccountId": "001xx",
    "Current_Staff__c": True,
    "UP_Commons_Eligible__c": True,
}
SETTINGS = {
    "UP_ECA_CONSUMER_KEY": "consumer-key",
    "UP_ECA_CONSUMER_SECRET": "consumer-secret",
    "UP_ECA_LOGIN_URL": "https://example.my.salesforce.com",
    "UP_ECA_API_VERSION": "v62.0",
}


@override_settings(**SETTINGS)
class CommandTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))
        patcher = mock.patch(
            "requests.Session.request",
            side_effect=self.session.request,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, name, *args, **kwargs):
        out = StringIO()
        call_command(name, *args, stdout=out, stderr=StringIO(), **kwargs)
        return out.getvalue()


class TokenCommandTests(CommandTestBase):
    def test_prints_instance_url_and_masked_token(self):
        out = self.call("up_eca_token")
        self.assertIn(INSTANCE_URL, out)
        self.assertNotIn(TOKEN_BODY["access_token"], out)
        self.assertIn(TOKEN_BODY["access_token"][:4], out)

    def test_reports_cache_source(self):
        first = self.call("up_eca_token")
        second = self.call("up_eca_token")
        self.assertIn("fresh", first.lower())
        self.assertIn("cache", second.lower())
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)

    def test_refresh_flag_forces_new_token(self):
        self.call("up_eca_token")
        self.session.add(
            "POST",
            TOKEN_URL,
            FakeResponse(200, {**TOKEN_BODY, "access_token": "brand-new-tok"}),
        )
        out = self.call("up_eca_token", "--refresh")
        self.assertIn("bran", out)
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 2)

    def test_json_output(self):
        out = self.call("up_eca_token", "--json")
        data = json.loads(out)
        self.assertEqual(data["instance_url"], INSTANCE_URL)
        self.assertNotEqual(data["access_token"], TOKEN_BODY["access_token"])

    @override_settings(UP_ECA_CONSUMER_KEY="", UP_ECA_CONSUMER_SECRET="")
    def test_missing_configuration_is_a_command_error(self):
        with self.assertRaises(CommandError) as ctx:
            self.call("up_eca_token")
        self.assertIn("UP_ECA_CONSUMER_KEY", str(ctx.exception))

    def test_rejected_credentials_are_a_command_error(self):
        self.session.add(
            "POST",
            TOKEN_URL,
            FakeResponse(
                400, {"error": "invalid_client", "error_description": "bad"}
            ),
        )
        with self.assertRaises(CommandError) as ctx:
            self.call("up_eca_token")
        self.assertIn("invalid_client", str(ctx.exception))


class WhoamiCommandTests(CommandTestBase):
    def test_prints_run_as_user_details(self):
        self.session.add(
            "GET",
            f"{INSTANCE_URL}/services/oauth2/userinfo",
            FakeResponse(
                200,
                {
                    "user_id": "005xx",
                    "organization_id": "00Dxx",
                    "preferred_username": "integration@aupresses.org",
                    "name": "Integration User",
                    "email": "integration@aupresses.org",
                },
            ),
        )
        out = self.call("up_eca_whoami")
        self.assertIn("integration@aupresses.org", out)
        self.assertIn("005xx", out)
        self.assertIn("00Dxx", out)

    def test_json_output(self):
        payload = {"user_id": "005xx", "preferred_username": "u"}
        self.session.add(
            "GET",
            f"{INSTANCE_URL}/services/oauth2/userinfo",
            FakeResponse(200, payload),
        )
        self.assertEqual(
            json.loads(self.call("up_eca_whoami", "--json")), payload
        )


class LimitsCommandTests(CommandTestBase):
    LIMITS = {
        "DailyApiRequests": {"Max": 15000, "Remaining": 14990},
        "DailyBulkApiBatches": {"Max": 15000, "Remaining": 15000},
    }

    def test_prints_daily_api_requests(self):
        self.session.add(
            "GET", f"{DATA}/limits", FakeResponse(200, self.LIMITS)
        )
        out = self.call("up_eca_limits")
        self.assertIn("DailyApiRequests", out)
        self.assertIn("14990", out)
        self.assertIn("15000", out)

    def test_json_output(self):
        self.session.add(
            "GET", f"{DATA}/limits", FakeResponse(200, self.LIMITS)
        )
        self.assertEqual(
            json.loads(self.call("up_eca_limits", "--json")), self.LIMITS
        )

    def test_api_error_is_a_command_error(self):
        self.session.add(
            "GET",
            f"{DATA}/limits",
            FakeResponse(
                403, [{"errorCode": "API_DISABLED_FOR_ORG", "message": "no"}]
            ),
        )
        with self.assertRaises(CommandError) as ctx:
            self.call("up_eca_limits")
        self.assertIn("API_DISABLED_FOR_ORG", str(ctx.exception))


class QueryCommandTests(CommandTestBase):
    RESULT = {"totalSize": 1, "done": True, "records": [CONTACT]}

    def test_runs_given_soql_and_prints_records(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, self.RESULT))
        out = self.call("up_eca_query", "SELECT Id, Name FROM Contact LIMIT 1")
        call = self.session.calls_to(QUERY_URL)[0]
        self.assertEqual(
            call["params"]["q"], "SELECT Id, Name FROM Contact LIMIT 1"
        )
        self.assertIn("Ada Lovelace", out)
        self.assertIn("003xx", out)

    def test_default_query_targets_contact(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, self.RESULT))
        self.call("up_eca_query")
        self.assertIn(
            "FROM Contact", self.session.calls_to(QUERY_URL)[0]["params"]["q"]
        )

    def test_json_output_is_records_list(self):
        self.session.add("GET", QUERY_URL, FakeResponse(200, self.RESULT))
        data = json.loads(
            self.call("up_eca_query", "SELECT Id FROM Contact", "--json")
        )
        self.assertEqual(data["records"][0]["Id"], "003xx")
        self.assertEqual(data["totalSize"], 1)

    def test_all_flag_follows_pagination(self):
        next_path = "/services/data/v62.0/query/01gxx-1"
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200,
                {
                    "totalSize": 2,
                    "done": False,
                    "nextRecordsUrl": next_path,
                    "records": [{"Id": "a"}],
                },
            ),
        )
        self.session.add(
            "GET",
            f"{INSTANCE_URL}{next_path}",
            FakeResponse(
                200, {"totalSize": 2, "done": True, "records": [{"Id": "b"}]}
            ),
        )
        out = self.call("up_eca_query", "SELECT Id FROM Contact", "--all")
        self.assertIn('"a"', out)
        self.assertIn('"b"', out)

    def test_malformed_query_is_a_command_error(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                400, [{"errorCode": "MALFORMED_QUERY", "message": "oops"}]
            ),
        )
        with self.assertRaises(CommandError) as ctx:
            self.call("up_eca_query", "SELEC nonsense")
        self.assertIn("MALFORMED_QUERY", str(ctx.exception))


class LookupCommandTests(CommandTestBase):
    def test_lookup_by_email_reports_eligible_member(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200, {"totalSize": 1, "done": True, "records": [CONTACT]}
            ),
        )
        out = self.call("up_eca_lookup", "ada@example.org")
        self.assertIn("ada@example.org", out)
        self.assertIn("001xx", out)
        self.assertIn("Ada Lovelace", out)
        self.assertRegex(out.lower(), r"eligible|active")

    def test_lookup_reports_ineligible_contact(self):
        record = {**CONTACT, "UP_Commons_Eligible__c": False}
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200, {"totalSize": 1, "done": True, "records": [record]}
            ),
        )
        out = self.call("up_eca_lookup", "ada@example.org")
        self.assertRegex(out.lower(), r"not eligible|inactive")

    def test_lookup_reports_no_match(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(200, {"totalSize": 0, "done": True, "records": []}),
        )
        out = self.call("up_eca_lookup", "nobody@example.org")
        self.assertRegex(out.lower(), r"no (contact|account) found|not found")

    def test_lookup_by_username_uses_all_profile_emails(self):
        Profile.objects.create(
            username="ada",
            email="primary@example.org",
            emails=["ada@example.org"],
        )
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(200, {"totalSize": 0, "done": True, "records": []}),
            FakeResponse(
                200, {"totalSize": 1, "done": True, "records": [CONTACT]}
            ),
        )
        out = self.call("up_eca_lookup", "--username", "ada")
        queried = [c["params"]["q"] for c in self.session.calls_to(QUERY_URL)]
        self.assertTrue(any("primary@example.org" in q for q in queried))
        self.assertTrue(any("ada@example.org" in q for q in queried))
        self.assertIn("001xx", out)

    def test_unknown_username_is_a_command_error(self):
        with self.assertRaises(CommandError):
            self.call("up_eca_lookup", "--username", "ghost")

    def test_no_arguments_is_a_command_error(self):
        with self.assertRaises(CommandError):
            self.call("up_eca_lookup")

    def test_json_output(self):
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200, {"totalSize": 1, "done": True, "records": [CONTACT]}
            ),
        )
        data = json.loads(
            self.call("up_eca_lookup", "ada@example.org", "--json")
        )
        self.assertTrue(data["found"])
        self.assertTrue(data["eligible"])
        self.assertEqual(data["account_id"], "001xx")
