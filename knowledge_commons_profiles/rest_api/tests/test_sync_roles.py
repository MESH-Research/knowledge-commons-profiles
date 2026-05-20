"""
Tests for ExternalSync._handle_comanage_roles role mapping.

Covers the bug where two simultaneous COmanage roles (e.g. HASTAC and
STEMED+) overwrite each other's is_member_of values because the mapping
dict was iterated inside the role loop.
"""

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
