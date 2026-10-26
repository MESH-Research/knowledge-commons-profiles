from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceError,
)
from knowledge_commons_profiles.up_salesforce.schemas import Contact
from knowledge_commons_profiles.up_salesforce.schemas import QueryResponse
from knowledge_commons_profiles.up_salesforce.sync import MembershipLookup
from knowledge_commons_profiles.up_salesforce.sync import UPExternalClientApp


def contact_record(**overrides):
    record = {
        "attributes": {"type": "Contact", "url": "/x"},
        "Id": "003xx",
        "Name": "Ada Lovelace",
        "Email": "ada@example.org",
        "AccountId": "001xx",
        "Current_Staff__c": True,
        "UP_Commons_Eligible__c": True,
    }
    record.update(overrides)
    return record


def query_result(*records):
    return {"totalSize": len(records), "done": True, "records": list(records)}


EMPTY = query_result()


class UPExternalClientAppTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.client = mock.Mock()
        self.client.query.return_value = query_result(contact_record())
        self.up = UPExternalClientApp(client=self.client)

    def test_is_a_sync_class(self):
        self.assertIsInstance(self.up, SyncClass)

    def test_search_multiple_returns_parsed_contacts_under_up_key(self):
        result = self.up.search_multiple(["ada@example.org"])
        response = result["UP"]
        self.assertIsInstance(response, QueryResponse)
        self.assertEqual(response.totalSize, 1)
        self.assertIsInstance(response.records[0], Contact)
        self.assertEqual(response.records[0].AccountId, "001xx")

    def test_search_multiple_queries_contact_by_quoted_email(self):
        self.up.search_multiple(["ada@example.org"])
        soql = self.client.query.call_args.args[0]
        self.assertIn("FROM Contact", soql)
        self.assertIn("Email = 'ada@example.org'", soql)
        self.assertIn("UP_Commons_Eligible__c", soql)
        self.assertIn("AccountId", soql)

    def test_email_is_normalised_before_query(self):
        self.up.search_multiple(["  Ada@Example.ORG "])
        soql = self.client.query.call_args.args[0]
        self.assertIn("'ada@example.org'", soql)

    def test_apostrophe_in_email_is_escaped(self):
        self.up.search_multiple(["o'brien@example.org"])
        soql = self.client.query.call_args.args[0]
        self.assertIn(r"'o\'brien@example.org'", soql)

    def test_invalid_emails_are_skipped(self):
        result = self.up.search_multiple(["not-an-email", "", None])
        self.assertIsNone(result["UP"])
        self.client.query.assert_not_called()

    def test_first_hit_wins_and_later_emails_are_not_queried(self):
        self.up.search_multiple(["ada@example.org", "second@example.org"])
        self.assertEqual(self.client.query.call_count, 1)

    def test_falls_through_to_next_email_when_no_hit(self):
        self.client.query.side_effect = [
            EMPTY,
            query_result(contact_record(Email="second@example.org")),
        ]
        result = self.up.search_multiple(
            ["none@example.org", "second@example.org"]
        )
        self.assertEqual(result["UP"].records[0].Email, "second@example.org")

    def test_api_error_for_one_email_continues_to_the_next(self):
        self.client.query.side_effect = [
            UPSalesforceError("boom"),
            query_result(contact_record()),
        ]
        result = self.up.search_multiple(["bad@example.org", "ada@example.org"])
        self.assertEqual(result["UP"].totalSize, 1)

    def test_no_match_anywhere_returns_none(self):
        self.client.query.return_value = EMPTY
        self.assertEqual(
            self.up.search_multiple(["x@example.org"]), {"UP": None}
        )

    def test_search_single_email_delegates(self):
        result = self.up.search("ada@example.org")
        self.assertEqual(result["UP"].totalSize, 1)

    def test_search_results_are_cached_per_email(self):
        self.up.search_multiple(["ada@example.org"])
        UPExternalClientApp(client=self.client).search_multiple(
            ["ada@example.org"]
        )
        self.assertEqual(self.client.query.call_count, 1)

    def test_malformed_payload_is_treated_as_no_match(self):
        self.client.query.return_value = {"unexpected": True}
        self.assertEqual(
            self.up.search_multiple(["ada@example.org"]), {"UP": None}
        )

    def test_get_sync_id_is_account_id(self):
        response = self.up.search_multiple(["ada@example.org"])["UP"]
        self.assertEqual(self.up.get_sync_id(response), "001xx")

    def test_get_sync_id_of_none_or_empty_is_none(self):
        self.assertIsNone(self.up.get_sync_id(None))
        empty = QueryResponse[Contact](totalSize=0, done=True, records=[])
        self.assertIsNone(self.up.get_sync_id(empty))

    def test_is_member_true_when_eligible(self):
        self.up.search_multiple(["ada@example.org"])
        self.assertTrue(self.up.is_member("001xx"))

    def test_is_member_false_when_not_eligible(self):
        self.client.query.return_value = query_result(
            contact_record(UP_Commons_Eligible__c=False)
        )
        self.up.search_multiple(["ada@example.org"])
        self.assertFalse(self.up.is_member("001xx"))

    def test_is_member_false_when_eligibility_missing(self):
        self.client.query.return_value = query_result(
            contact_record(UP_Commons_Eligible__c=None)
        )
        self.up.search_multiple(["ada@example.org"])
        self.assertFalse(self.up.is_member("001xx"))

    def test_is_member_false_without_prior_search(self):
        self.assertFalse(self.up.is_member("001xx"))

    def test_get_user_info_returns_contacts_from_search(self):
        self.up.search_multiple(["ada@example.org"])
        info = self.up.get_user_info("001xx")
        self.assertEqual(info[0].Id, "003xx")

    def test_groups_is_empty(self):
        self.assertEqual(self.up.groups("001xx"), [])

    def test_lookup_found_and_eligible(self):
        summary = self.up.lookup(["ada@example.org"])
        self.assertIsInstance(summary, MembershipLookup)
        self.assertTrue(summary.found)
        self.assertTrue(summary.eligible)
        self.assertEqual(summary.account_id, "001xx")
        self.assertEqual(summary.matched_email, "ada@example.org")
        self.assertEqual(summary.contact.Name, "Ada Lovelace")

    def test_lookup_not_found(self):
        self.client.query.return_value = EMPTY
        summary = self.up.lookup(["x@example.org"])
        self.assertFalse(summary.found)
        self.assertFalse(summary.eligible)
        self.assertIsNone(summary.contact)
        self.assertIsNone(summary.matched_email)
