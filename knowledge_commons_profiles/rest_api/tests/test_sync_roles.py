"""
Tests for ExternalSync._handle_comanage_roles role mapping.

Covers the bug where two simultaneous COmanage roles (e.g. HASTAC and
STEMED+) overwrite each other's is_member_of values because the mapping
dict was iterated inside the role loop.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus
from knowledge_commons_profiles.rest_api.sync import ExternalSync

User = get_user_model()


SOCIETY_MAPPINGS = {"hastac": "HASTAC", "stemedplus": "STEMED+"}


class HandleComanageRolesTests(TestCase):
    """Tests for ExternalSync._handle_comanage_roles()."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="bonnie", email="bonnie@example.test"
        )
        self.profile = Profile.objects.create(
            username="bonnie", email="bonnie@example.test"
        )
        self.person = Person.objects.create(
            display_name="Bonnie", user=self.profile
        )
        self.co_hastac = CO.objects.create(
            id=17, name="HASTAC", slug="hastac"
        )
        self.co_stemedplus = CO.objects.create(
            id=18, name="STEMEDPLUS", slug="stemedplus"
        )

    def _make_role(self, co, organization, affiliation="member"):
        return Role.objects.create(
            person=self.person,
            co=co,
            affiliation=affiliation,
            status=RoleStatus.ACTIVE,
            organization=organization,
            source_system="co-manage",
        )

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_hastac_only_sets_hastac_true_and_stemed_false(self):
        self._make_role(self.co_hastac, "Hastac")
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertTrue(member_data["HASTAC"])
        self.assertFalse(member_data["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_stemedplus_only_sets_stemed_true_and_hastac_false(self):
        self._make_role(self.co_stemedplus, "Stemedplus")
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertTrue(member_data["STEMED+"])
        self.assertFalse(member_data["HASTAC"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_both_roles_set_both_true(self):
        """Regression: two roles must not overwrite each other."""
        self._make_role(self.co_hastac, "Hastac")
        self._make_role(self.co_stemedplus, "Stemedplus")
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertTrue(member_data["HASTAC"])
        self.assertTrue(member_data["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_non_member_affiliation_does_not_count(self):
        self._make_role(self.co_hastac, "Hastac", affiliation="staff")
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertFalse(member_data["HASTAC"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_no_roles_sets_all_false(self):
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertFalse(member_data["HASTAC"])
        self.assertFalse(member_data["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_organization_case_insensitive(self):
        self._make_role(self.co_hastac, "HASTAC")
        member_data: dict = {}
        ExternalSync._handle_comanage_roles(member_data, self.profile)
        self.assertTrue(member_data["HASTAC"])


class RefreshLocalMembershipsTests(TestCase):
    """Tests for ExternalSync.refresh_local_memberships()."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="carl", email="carl@example.test"
        )
        self.person = Person.objects.create(
            display_name="Carl", user=self.profile
        )
        self.co_hastac = CO.objects.create(
            id=27, name="HASTAC", slug="hastac"
        )
        self.co_stemedplus = CO.objects.create(
            id=28, name="STEMEDPLUS", slug="stemedplus"
        )

    def _make_role(self, co, organization, affiliation="member"):
        return Role.objects.create(
            person=self.person,
            co=co,
            affiliation=affiliation,
            status=RoleStatus.ACTIVE,
            organization=organization,
            source_system="co-manage",
        )

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_returns_updated_membership_dict(self):
        self._make_role(self.co_hastac, "Hastac")
        result = ExternalSync.refresh_local_memberships(self.profile)
        self.assertTrue(result["HASTAC"])
        self.assertFalse(result["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_writes_membership_json_to_profile(self):
        self._make_role(self.co_hastac, "Hastac")
        self._make_role(self.co_stemedplus, "Stemedplus")
        ExternalSync.refresh_local_memberships(self.profile)
        self.profile.refresh_from_db()
        stored = json.loads(self.profile.is_member_of)
        self.assertTrue(stored["HASTAC"])
        self.assertTrue(stored["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_preserves_external_society_keys(self):
        """MLA/MSU/etc. keys must survive the refresh untouched."""
        self.profile.is_member_of = json.dumps(
            {"MLA": True, "MSU": False, "STEMED+": False}
        )
        self.profile.save()
        self._make_role(self.co_hastac, "Hastac")
        result = ExternalSync.refresh_local_memberships(self.profile)
        self.assertTrue(result["MLA"])
        self.assertFalse(result["MSU"])
        self.assertTrue(result["HASTAC"])
        self.assertFalse(result["STEMED+"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_handles_null_is_member_of(self):
        self.profile.is_member_of = None
        self.profile.save()
        self._make_role(self.co_hastac, "Hastac")
        result = ExternalSync.refresh_local_memberships(self.profile)
        self.assertTrue(result["HASTAC"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_handles_malformed_is_member_of(self):
        self.profile.is_member_of = "not json"
        self.profile.save()
        self._make_role(self.co_hastac, "Hastac")
        result = ExternalSync.refresh_local_memberships(self.profile)
        self.assertTrue(result["HASTAC"])

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_does_not_make_external_http_calls(self):
        self._make_role(self.co_hastac, "Hastac")
        with patch(
            "knowledge_commons_profiles.rest_api.sync.requests.get"
        ) as mock_get:
            ExternalSync.refresh_local_memberships(self.profile)
        mock_get.assert_not_called()

    @override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
    def test_does_not_bump_last_sync(self):
        self._make_role(self.co_hastac, "Hastac")
        original = self.profile.last_sync
        ExternalSync.refresh_local_memberships(self.profile)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.last_sync, original)
