"""
The dry-run preview must compute exactly what a sync would write and must
write nothing.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus
from knowledge_commons_profiles.up_salesforce.dry_run import RoleChange
from knowledge_commons_profiles.up_salesforce.dry_run import SyncPreview
from knowledge_commons_profiles.up_salesforce.dry_run import preview_sync
from knowledge_commons_profiles.up_salesforce.schemas import Contact
from knowledge_commons_profiles.up_salesforce.schemas import QueryResponse
from knowledge_commons_profiles.up_salesforce.tests.support import INSTANCE_URL
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_BODY
from knowledge_commons_profiles.up_salesforce.tests.support import TOKEN_URL
from knowledge_commons_profiles.up_salesforce.tests.support import FakeResponse
from knowledge_commons_profiles.up_salesforce.tests.support import FakeSession

User = get_user_model()
UP_ORG = "Association of American University Presses"
QUERY_URL = f"{INSTANCE_URL}/services/data/v62.0/query"
CONTACT = {
    "attributes": {"type": "Contact", "url": "/x"},
    "Id": "003xx",
    "Name": "Ada Lovelace",
    "Email": "ada@example.org",
    "AccountId": "001xx",
    "Current_Staff__c": True,
    "UP_Commons_Eligible__c": True,
}


def make_profile(username="ada", **fields):
    User.objects.create_user(username=username, email=f"{username}@example.org")
    defaults = {"email": f"{username}@example.org", "emails": []}
    defaults.update(fields)
    return Profile.objects.create(username=username, **defaults)


def make_role(profile, organization=UP_ORG, status=RoleStatus.EXPIRED):
    person = Person.objects.create(display_name=profile.username, user=profile)
    co, _ = CO.objects.get_or_create(
        id=99, defaults={"name": "UP", "slug": "up"}
    )
    return Role.objects.create(
        person=person,
        co=co,
        affiliation="member",
        status=status,
        organization=organization,
        source_system="co-manage",
    )


class FakeSyncClass:
    """A SyncClass-shaped double driven by canned answers."""

    def __init__(self, account_id="001xx", member=True, groups=None):
        self.account_id = account_id
        self.member = member
        self._groups = groups or []
        self.searched_emails = None

    def search_multiple(self, emails):
        self.searched_emails = list(emails)
        if self.account_id is None:
            return {"UP": None}
        record = Contact(**{**CONTACT, "AccountId": self.account_id})
        return {
            "UP": QueryResponse[Contact](
                totalSize=1, done=True, records=[record]
            )
        }

    def get_sync_id(self, response):
        return response.records[0].AccountId if response else None

    def is_member(self, sync_id):
        return self.member

    def groups(self, sync_id):
        return list(self._groups)


class PreviewSyncTests(TestCase):
    def test_preview_reports_new_values_for_member(self):
        profile = make_profile()
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertIsInstance(preview, SyncPreview)
        self.assertEqual(preview.username, "ada")
        self.assertEqual(preview.sync_id, "001xx")
        self.assertTrue(preview.is_member)
        self.assertEqual(preview.groups, [])

    def test_preview_searches_with_every_profile_email(self):
        profile = make_profile(emails=["alt@example.org"])
        sync = FakeSyncClass()
        preview_sync(profile, sync, [UP_ORG])
        self.assertEqual(
            sync.searched_emails, ["ada@example.org", "alt@example.org"]
        )

    def test_preview_reports_current_values_from_profile(self):
        profile = make_profile(
            external_sync_ids=json.dumps({"UP": "001OLD"}),
            is_member_of=json.dumps({"UP": False}),
            in_membership_groups=json.dumps({"UP": ["x"]}),
        )
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertEqual(preview.current_sync_id, "001OLD")
        self.assertFalse(preview.current_is_member)
        self.assertEqual(preview.current_groups, ["x"])
        self.assertTrue(preview.would_change)

    def test_preview_with_no_prior_sync_has_none_current_values(self):
        profile = make_profile()
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertIsNone(preview.current_sync_id)
        self.assertIsNone(preview.current_is_member)
        self.assertIsNone(preview.current_groups)

    def test_preview_with_malformed_json_treats_as_no_prior_sync(self):
        profile = make_profile(is_member_of="not json")
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertIsNone(preview.current_is_member)

    def test_preview_unchanged_when_values_match(self):
        profile = make_profile(
            external_sync_ids=json.dumps({"UP": "001xx"}),
            is_member_of=json.dumps({"UP": True}),
            in_membership_groups=json.dumps({"UP": []}),
        )
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertFalse(preview.would_change)

    def test_preview_not_found(self):
        profile = make_profile()
        preview = preview_sync(
            profile, FakeSyncClass(account_id=None), [UP_ORG]
        )
        self.assertIsNone(preview.sync_id)
        self.assertFalse(preview.is_member)
        self.assertEqual(preview.groups, [])

    def test_role_change_for_up_role_expired_to_active(self):
        profile = make_profile()
        role = make_role(profile, status=RoleStatus.EXPIRED)
        preview = preview_sync(profile, FakeSyncClass(member=True), [UP_ORG])
        self.assertEqual(len(preview.role_changes), 1)
        change = preview.role_changes[0]
        self.assertIsInstance(change, RoleChange)
        self.assertEqual(change.role_id, role.id)
        self.assertEqual(change.current_status, RoleStatus.EXPIRED)
        self.assertEqual(change.new_status, RoleStatus.ACTIVE)
        self.assertTrue(change.changed)

    def test_role_change_for_non_member_is_expired(self):
        profile = make_profile()
        make_role(profile, status=RoleStatus.ACTIVE)
        preview = preview_sync(profile, FakeSyncClass(member=False), [UP_ORG])
        self.assertEqual(preview.role_changes[0].new_status, RoleStatus.EXPIRED)

    def test_role_already_correct_is_reported_unchanged(self):
        profile = make_profile()
        make_role(profile, status=RoleStatus.ACTIVE)
        preview = preview_sync(profile, FakeSyncClass(member=True), [UP_ORG])
        self.assertFalse(preview.role_changes[0].changed)

    def test_roles_for_other_organizations_are_ignored(self):
        profile = make_profile()
        make_role(profile, organization="Modern Language Association")
        preview = preview_sync(profile, FakeSyncClass(), [UP_ORG])
        self.assertEqual(preview.role_changes, [])

    def test_preview_writes_nothing(self):
        profile = make_profile(
            is_member_of=json.dumps({"UP": False}),
            external_sync_ids=json.dumps({"UP": None}),
        )
        role = make_role(profile, status=RoleStatus.EXPIRED)
        before = Profile.objects.filter(pk=profile.pk).values().get()

        preview_sync(profile, FakeSyncClass(member=True), [UP_ORG])

        after = Profile.objects.filter(pk=profile.pk).values().get()
        role.refresh_from_db()
        self.assertEqual(before, after)
        self.assertEqual(role.status, RoleStatus.EXPIRED)


@override_settings(
    UP_ECA_CONSUMER_KEY="consumer-key",
    UP_ECA_CONSUMER_SECRET="consumer-secret",
    UP_ECA_LOGIN_URL="https://example.my.salesforce.com",
    UP_ECA_API_VERSION="v62.0",
)
class DryRunCommandTests(TestCase):
    """The command drives the real token/client/sync code over a fake HTTP
    boundary and must leave the database untouched."""

    def setUp(self):
        cache.clear()
        self.session = FakeSession()
        self.session.add("POST", TOKEN_URL, FakeResponse(200, TOKEN_BODY))
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                200, {"totalSize": 1, "done": True, "records": [CONTACT]}
            ),
        )
        patcher = mock.patch(
            "requests.Session.request", side_effect=self.session.request
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "up_eca_dry_run_sync",
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_reports_computed_sync_for_username(self):
        make_profile()
        out = self.call("--username", "ada")
        self.assertIn("ada", out)
        self.assertIn("001xx", out)
        self.assertRegex(out.lower(), r"member|eligible")
        self.assertRegex(
            out.lower(), r"dry.run|no changes (were )?written|read.only"
        )

    def test_reports_role_transition(self):
        profile = make_profile()
        make_role(profile, status=RoleStatus.EXPIRED)
        out = self.call("--username", "ada")
        self.assertIn(RoleStatus.EXPIRED, out)
        self.assertIn(RoleStatus.ACTIVE, out)

    def test_database_is_untouched(self):
        profile = make_profile(is_member_of=json.dumps({"UP": False}))
        role = make_role(profile, status=RoleStatus.EXPIRED)
        before = Profile.objects.filter(pk=profile.pk).values().get()

        self.call("--username", "ada")

        after = Profile.objects.filter(pk=profile.pk).values().get()
        role.refresh_from_db()
        self.assertEqual(before, after)
        self.assertEqual(role.status, RoleStatus.EXPIRED)

    def test_authenticates_and_queries_salesforce(self):
        make_profile()
        self.call("--username", "ada")
        self.assertEqual(len(self.session.calls_to(TOKEN_URL)), 1)
        self.assertEqual(len(self.session.calls_to(QUERY_URL)), 1)
        self.assertIn(
            "ada@example.org",
            self.session.calls_to(QUERY_URL)[0]["params"]["q"],
        )

    def test_multiple_usernames(self):
        make_profile("ada")
        make_profile("bob")
        out = self.call("--username", "ada", "--username", "bob")
        self.assertIn("ada", out)
        self.assertIn("bob", out)

    def test_all_with_limit(self):
        for name in ("ada", "bob", "cyd"):
            make_profile(name)
        out = self.call("--all", "--limit", "2")
        self.assertEqual(len(self.session.calls_to(QUERY_URL)), 2)
        self.assertIn("ada", out)

    def test_json_output(self):
        make_profile()
        data = json.loads(self.call("--username", "ada", "--json"))
        self.assertEqual(data[0]["username"], "ada")
        self.assertEqual(data[0]["sync_id"], "001xx")
        self.assertTrue(data[0]["is_member"])

    def test_unknown_username_is_an_error(self):
        with self.assertRaises(CommandError):
            self.call("--username", "ghost")

    def test_no_selection_is_an_error(self):
        with self.assertRaises(CommandError):
            self.call()

    def test_salesforce_failure_is_reported_not_raised_per_profile(self):
        make_profile()
        self.session.add(
            "GET",
            QUERY_URL,
            FakeResponse(
                500, [{"errorCode": "UNKNOWN_EXCEPTION", "message": "x"}]
            ),
        )
        out = self.call("--username", "ada")
        self.assertIn("ada", out)
        self.assertRegex(out.lower(), r"not found|no contact|non-member|false")
