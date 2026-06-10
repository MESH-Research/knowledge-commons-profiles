"""
Tests for get_external_memberships, the canonical final-roles merge.

Covers the read-time overlay of the manual role_overrides layer onto the
synced is_member_of JSON — in particular that overrides still apply when
a profile has never been synced (is_member_of None or empty), and that
api_only=True never includes the manual layer.
"""

import json

from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.utils import get_external_memberships


class GetExternalMembershipsTests(TestCase):
    def _profile(self, is_member_of=None, role_overrides=None):
        return Profile.objects.create(
            username="bonnie",
            is_member_of=is_member_of,
            role_overrides=role_overrides or [],
        )

    def test_merges_overrides_onto_synced_memberships(self):
        profile = self._profile(
            is_member_of=json.dumps({"HASTAC": True, "STEMED+": False}),
            role_overrides=["STEMED+"],
        )
        self.assertEqual(
            get_external_memberships(profile),
            {"HASTAC": True, "STEMED+": True},
        )

    def test_overrides_apply_when_is_member_of_is_none(self):
        profile = self._profile(
            is_member_of=None, role_overrides=["STEMED+"]
        )
        self.assertEqual(
            get_external_memberships(profile), {"STEMED+": True}
        )

    def test_overrides_apply_when_is_member_of_is_empty_string(self):
        profile = self._profile(
            is_member_of="", role_overrides=["STEMED+"]
        )
        self.assertEqual(
            get_external_memberships(profile), {"STEMED+": True}
        )

    def test_no_data_at_all_returns_empty(self):
        profile = self._profile(is_member_of=None, role_overrides=[])
        self.assertEqual(get_external_memberships(profile), {})

    def test_api_only_never_includes_overrides(self):
        profile = self._profile(
            is_member_of=json.dumps({"HASTAC": True}),
            role_overrides=["STEMED+"],
        )
        self.assertEqual(
            get_external_memberships(profile, api_only=True),
            {"HASTAC": True},
        )

    def test_api_only_with_no_sync_data_returns_empty(self):
        profile = self._profile(
            is_member_of=None, role_overrides=["STEMED+"]
        )
        self.assertEqual(
            get_external_memberships(profile, api_only=True), {}
        )

    def test_malformed_json_returns_empty(self):
        profile = self._profile(
            is_member_of="{not json", role_overrides=["STEMED+"]
        )
        self.assertEqual(get_external_memberships(profile), {})
