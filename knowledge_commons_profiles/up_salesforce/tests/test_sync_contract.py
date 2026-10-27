"""
One behavioural contract, two implementations.

These tests describe what ``ExternalSync`` needs from the UP sync class
(``search_multiple`` -> ``get_sync_id`` -> ``is_member`` / ``groups``) in
terms of inputs and outputs only. The same tests run against the legacy
``cilogon.sync_apis.up.UP`` and the new ``UPExternalClientApp``; only the
HTTP boundary is faked, differently for each because they authenticate
differently.
"""

from __future__ import annotations

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.sync_apis import up as legacy_up
from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus
from knowledge_commons_profiles.rest_api import sync as rest_sync
from knowledge_commons_profiles.up_salesforce.sync import UPExternalClientApp
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

User = get_user_model()

UP_ORG = "Association of American University Presses"


def contact(**overrides):
    record = {
        "attributes": {
            "type": "Contact",
            "url": "/services/data/v62.0/sobjects/Contact/003xx",
        },
        "Id": "003xx",
        "Name": "Ada Lovelace",
        "Email": "ada@example.org",
        "AccountId": "001xx",
        "Current_Staff__c": True,
        "UP_Commons_Eligible__c": True,
    }
    record.update(overrides)
    return record


def hit(*records):
    return FakeResponse(
        200, {"totalSize": len(records), "done": True, "records": records}
    )


def miss():
    return hit()


def server_error():
    return FakeResponse(
        500,
        [{"errorCode": "UNKNOWN_EXCEPTION", "message": "boom"}],
    )


class UPSyncContractMixin:
    """
    Behavioural tests shared by both implementations. Subclasses provide
    ``make_sync()``, ``respond(*responses)``, ``query_calls()`` and
    ``last_soql()``.
    """

    # --- search_multiple ---------------------------------------------------

    def test_hit_returns_response_under_up_key(self):
        self.respond(hit(contact()))
        result = self.make_sync().search_multiple(["ada@example.org"])
        self.assertEqual(set(result), {"UP"})
        self.assertEqual(result["UP"].totalSize, 1)
        self.assertEqual(result["UP"].records[0].AccountId, "001xx")
        self.assertEqual(result["UP"].records[0].Id, "003xx")

    def test_miss_returns_none_under_up_key(self):
        self.respond(miss())
        result = self.make_sync().search_multiple(["nobody@example.org"])
        self.assertEqual(result, {"UP": None})

    def test_invalid_emails_make_no_request_and_return_none(self):
        self.respond(hit(contact()))
        result = self.make_sync().search_multiple(
            ["not-an-email", "", "also bad@", None]
        )
        self.assertEqual(result, {"UP": None})
        self.assertEqual(self.query_calls(), 0)

    def test_first_email_hit_stops_searching(self):
        self.respond(hit(contact()))
        self.make_sync().search_multiple(
            ["ada@example.org", "second@example.org"]
        )
        self.assertEqual(self.query_calls(), 1)

    def test_falls_through_to_later_email_after_miss(self):
        self.respond(miss(), hit(contact(Email="second@example.org")))
        result = self.make_sync().search_multiple(
            ["first@example.org", "second@example.org"]
        )
        self.assertEqual(result["UP"].records[0].Email, "second@example.org")
        self.assertEqual(self.query_calls(), 2)

    def test_server_error_for_one_email_falls_through_to_next(self):
        self.respond(server_error(), hit(contact()))
        result = self.make_sync().search_multiple(
            ["first@example.org", "ada@example.org"]
        )
        self.assertEqual(result["UP"].totalSize, 1)

    def test_server_error_for_every_email_returns_none(self):
        self.respond(server_error())
        result = self.make_sync().search_multiple(["ada@example.org"])
        self.assertEqual(result, {"UP": None})

    def test_email_is_normalised_in_the_query_sent(self):
        self.respond(hit(contact()))
        self.make_sync().search_multiple(["  Ada@Example.ORG "])
        self.assertIn("ada@example.org", self.last_soql())
        self.assertNotIn("Ada@Example.ORG", self.last_soql())

    def test_query_targets_contact_by_email(self):
        self.respond(hit(contact()))
        self.make_sync().search_multiple(["ada@example.org"])
        soql = self.last_soql()
        self.assertIn("FROM Contact", soql)
        self.assertIn("Email", soql)
        self.assertIn("UP_Commons_Eligible__c", soql)
        self.assertIn("AccountId", soql)

    def test_repeat_search_for_same_email_is_served_from_cache(self):
        self.respond(hit(contact()))
        self.make_sync().search_multiple(["ada@example.org"])
        self.make_sync().search_multiple(["ada@example.org"])
        self.assertEqual(self.query_calls(), 1)

    # --- get_sync_id -------------------------------------------------------

    def test_get_sync_id_is_the_account_id(self):
        self.respond(hit(contact(AccountId="001ACCOUNT")))
        sync = self.make_sync()
        response = sync.search_multiple(["ada@example.org"])["UP"]
        self.assertEqual(sync.get_sync_id(response), "001ACCOUNT")

    def test_get_sync_id_of_none_is_none(self):
        self.assertIsNone(self.make_sync().get_sync_id(None))

    # --- is_member / groups / get_user_info --------------------------------

    def test_is_member_true_when_contact_is_commons_eligible(self):
        self.respond(hit(contact(UP_Commons_Eligible__c=True)))
        sync = self.make_sync()
        sync_id = sync.get_sync_id(
            sync.search_multiple(["ada@example.org"])["UP"]
        )
        self.assertTrue(sync.is_member(sync_id))

    def test_is_member_false_when_contact_is_not_eligible(self):
        self.respond(hit(contact(UP_Commons_Eligible__c=False)))
        sync = self.make_sync()
        sync_id = sync.get_sync_id(
            sync.search_multiple(["ada@example.org"])["UP"]
        )
        self.assertFalse(sync.is_member(sync_id))

    def test_is_member_false_when_eligibility_is_missing(self):
        self.respond(hit(contact(UP_Commons_Eligible__c=None)))
        sync = self.make_sync()
        sync_id = sync.get_sync_id(
            sync.search_multiple(["ada@example.org"])["UP"]
        )
        self.assertFalse(sync.is_member(sync_id))

    def test_is_member_false_when_nothing_was_found(self):
        self.respond(miss())
        sync = self.make_sync()
        sync.search_multiple(["nobody@example.org"])
        self.assertFalse(sync.is_member("001xx"))

    def test_groups_is_empty(self):
        self.respond(hit(contact()))
        sync = self.make_sync()
        sync.search_multiple(["ada@example.org"])
        self.assertEqual(sync.groups("001xx"), [])

    def test_get_user_info_returns_the_found_contacts(self):
        self.respond(hit(contact()))
        sync = self.make_sync()
        sync.search_multiple(["ada@example.org"])
        info = sync.get_user_info("001xx")
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0].Id, "003xx")
        self.assertEqual(info[0].AccountId, "001xx")

    # --- end to end through ExternalSync -----------------------------------

    def _profile_with_role(self, organization=UP_ORG):
        User.objects.create_user(username="ada", email="ada@example.org")
        profile = Profile.objects.create(
            username="ada", email="ada@example.org", emails=[]
        )
        person = Person.objects.create(display_name="Ada", user=profile)
        co = CO.objects.create(id=99, name="UP", slug="up")
        role = Role.objects.create(
            person=person,
            co=co,
            affiliation="member",
            status=RoleStatus.EXPIRED,
            organization=organization,
            source_system="co-manage",
        )
        return profile, role

    def _run_external_sync(self, profile):
        with mock.patch.dict(rest_sync.CLASS_LOOKUPS, {"UP": self.make_sync()}):
            return rest_sync.ExternalSync.sync(
                profile,
                class_list=[("UP", [UP_ORG])],
                send_webhook=False,
                cache=False,
                webhooks=False,
            )

    def test_external_sync_marks_eligible_contact_as_member(self):
        self.respond(hit(contact(UP_Commons_Eligible__c=True)))
        profile, role = self._profile_with_role()

        result = self._run_external_sync(profile)

        self.assertTrue(result["UP"])
        profile.refresh_from_db()
        role.refresh_from_db()
        self.assertTrue(json.loads(profile.is_member_of)["UP"])
        self.assertEqual(json.loads(profile.external_sync_ids)["UP"], "001xx")
        self.assertEqual(json.loads(profile.in_membership_groups)["UP"], [])
        self.assertEqual(role.status, RoleStatus.ACTIVE)

    def test_external_sync_marks_ineligible_contact_as_non_member(self):
        self.respond(hit(contact(UP_Commons_Eligible__c=False)))
        profile, role = self._profile_with_role()
        role.status = RoleStatus.ACTIVE
        role.save()

        result = self._run_external_sync(profile)

        self.assertFalse(result["UP"])
        role.refresh_from_db()
        self.assertEqual(role.status, RoleStatus.EXPIRED)

    def test_external_sync_with_no_contact_records_non_member(self):
        self.respond(miss())
        profile, _ = self._profile_with_role()

        result = self._run_external_sync(profile)

        self.assertFalse(result["UP"])
        profile.refresh_from_db()
        self.assertIsNone(json.loads(profile.external_sync_ids)["UP"])
        self.assertEqual(json.loads(profile.in_membership_groups)["UP"], [])


# ---------------------------------------------------------------------------
# Harness for the legacy refresh-token implementation
# ---------------------------------------------------------------------------

LEGACY_BASE = "https://legacy.example.my.salesforce.com/services/data/v39.0/"
LEGACY_QUERY_URL = LEGACY_BASE + "query"


@override_settings(
    UP_API_BASE_URL=LEGACY_BASE,
    UP_API_TOKEN="legacy-token",
    UP_CLIENT_ID="legacy-client",
    UP_CLIENT_SECRET="legacy-secret",
    UP_REFRESH_TOKEN="legacy-refresh",
    UP_CACHE_TIMEOUT=3600,
)
class LegacyUPContractTests(UPSyncContractMixin, TestCase):
    """The existing ``cilogon.sync_apis.up.UP`` against the contract."""

    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("GET", LEGACY_QUERY_URL, miss())
        post = mock.patch.object(
            legacy_up.requests,
            "post",
            return_value=FakeResponse(200, {"access_token": "refreshed"}),
        )
        post.start()
        self.addCleanup(post.stop)
        req = mock.patch(
            "requests.Session.request", side_effect=self.session.request
        )
        req.start()
        self.addCleanup(req.stop)

    def make_sync(self):
        return legacy_up.UP()

    def respond(self, *responses):
        self.session.add("GET", LEGACY_QUERY_URL, *responses)

    def query_calls(self):
        return len(self.session.calls_to(LEGACY_QUERY_URL))

    def last_soql(self):
        return self.session.calls_to(LEGACY_QUERY_URL)[-1]["params"]["q"]


# ---------------------------------------------------------------------------
# Harness for the External Client App implementation
# ---------------------------------------------------------------------------

ECA_QUERY_URL = f"{INSTANCE_URL}/services/data/v62.0/query"


@override_settings(
    UP_ECA_CONSUMER_KEY="consumer-key",
    UP_ECA_CONSUMER_SECRET="consumer-secret",
    UP_ECA_LOGIN_URL="https://example.my.salesforce.com",
    UP_ECA_API_VERSION="v62.0",
)
class ExternalClientAppContractTests(UPSyncContractMixin, TestCase):
    """The new ``UPExternalClientApp`` against the same contract."""

    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))
        self.session.add("GET", ECA_QUERY_URL, miss())
        req = mock.patch(
            "requests.Session.request", side_effect=self.session.request
        )
        req.start()
        self.addCleanup(req.stop)

    def make_sync(self):
        return UPExternalClientApp()

    def respond(self, *responses):
        self.session.add("GET", ECA_QUERY_URL, *responses)

    def query_calls(self):
        return len(self.session.calls_to(ECA_QUERY_URL))

    def last_soql(self):
        return self.session.calls_to(ECA_QUERY_URL)[-1]["params"]["q"]
