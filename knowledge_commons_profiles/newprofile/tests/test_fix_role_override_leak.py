"""Tests for the fix_role_override_leak management command."""

import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import Profile

SOCIETY_MAPPINGS = {"hastac": "HASTAC", "stemedplus": "STEMED+"}


@override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
class FixRoleOverrideLeakTests(TestCase):
    """``fix_role_override_leak`` recomputes Profile.is_member_of for
    every profile with non-empty role_overrides, so the leak written by
    the earlier buggy version of ``_handle_comanage_roles`` is undone
    without touching role_overrides itself."""

    def _run(self, *extra):
        out = StringIO()
        err = StringIO()
        call_command(
            "fix_role_override_leak", *extra, stdout=out, stderr=err
        )
        return out.getvalue()

    def test_clears_leaked_membership_from_is_member_of(self):
        """STEMED+ override + leaked is_member_of[STEMED+]=True →
        the cleanup flips is_member_of[STEMED+] back to False because
        there is no STEMED+ Role row."""
        profile = Profile.objects.create(
            username="leaky",
            email="leaky@example.test",
            emails=[],
            role_overrides=["STEMED+"],
            is_member_of=json.dumps({"STEMED+": True}),
        )
        self._run()
        profile.refresh_from_db()
        stored = json.loads(profile.is_member_of or "{}")
        self.assertFalse(stored.get("STEMED+", False))

    def test_preserves_role_overrides(self):
        """The override array itself is correct and must not be touched."""
        profile = Profile.objects.create(
            username="keep",
            email="keep@example.test",
            emails=[],
            role_overrides=["HASTAC", "STEMED+"],
            is_member_of=json.dumps({"HASTAC": True, "STEMED+": True}),
        )
        self._run()
        profile.refresh_from_db()
        self.assertEqual(
            sorted(profile.role_overrides), ["HASTAC", "STEMED+"]
        )

    def test_preserves_external_society_keys(self):
        """API-driven keys (MLA/MSU/etc) must survive the cleanup."""
        profile = Profile.objects.create(
            username="mixed",
            email="mixed@example.test",
            emails=[],
            role_overrides=["HASTAC"],
            is_member_of=json.dumps(
                {"MLA": True, "MSU": False, "HASTAC": True}
            ),
        )
        self._run()
        profile.refresh_from_db()
        stored = json.loads(profile.is_member_of)
        self.assertTrue(stored["MLA"])
        self.assertFalse(stored["MSU"])
        self.assertFalse(stored["HASTAC"])

    def test_skips_profiles_without_overrides(self):
        """Profiles with empty role_overrides are left untouched."""
        profile = Profile.objects.create(
            username="clean",
            email="clean@example.test",
            emails=[],
            role_overrides=[],
            is_member_of=json.dumps({"MLA": True, "HASTAC": True}),
        )
        self._run()
        profile.refresh_from_db()
        stored = json.loads(profile.is_member_of)
        # untouched — the value is exactly what we stored
        self.assertTrue(stored["MLA"])
        self.assertTrue(stored["HASTAC"])

    def test_dry_run_does_not_write(self):
        profile = Profile.objects.create(
            username="dry",
            email="dry@example.test",
            emails=[],
            role_overrides=["HASTAC"],
            is_member_of=json.dumps({"HASTAC": True}),
        )
        self._run("--dry-run")
        profile.refresh_from_db()
        stored = json.loads(profile.is_member_of)
        self.assertTrue(stored["HASTAC"])

    def test_idempotent(self):
        profile = Profile.objects.create(
            username="idem",
            email="idem@example.test",
            emails=[],
            role_overrides=["HASTAC"],
            is_member_of=json.dumps({"HASTAC": True}),
        )
        self._run()
        self._run()
        profile.refresh_from_db()
        stored = json.loads(profile.is_member_of or "{}")
        self.assertFalse(stored.get("HASTAC", False))
        self.assertIn("HASTAC", profile.role_overrides)
