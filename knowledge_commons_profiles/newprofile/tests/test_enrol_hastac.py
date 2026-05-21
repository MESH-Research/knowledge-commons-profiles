"""Tests for the enrol_hastac management command."""

import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus

SOCIETY_MAPPINGS = {"hastac": "HASTAC", "stemedplus": "STEMED+"}


def _write_file(emails):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(emails))
    return path


@override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
class EnrolHastacTests(TestCase):
    """``enrol_hastac`` enrols users by email and refreshes membership."""

    def setUp(self):
        self.alice = Profile.objects.create(
            username="alice",
            email="alice@example.test",
            emails=[],
        )
        self.bob = Profile.objects.create(
            username="bob",
            email="bob.primary@example.test",
            emails=["bob.alt@example.test"],
        )

    def _run(self, file_path, *extra):
        out = StringIO()
        err = StringIO()
        call_command(
            "enrol_hastac",
            file_path,
            *extra,
            stdout=out,
            stderr=err,
        )
        return out.getvalue()

    def test_enrols_user_matched_by_primary_email(self):
        path = _write_file(["alice@example.test"])
        self._run(path)

        roles = Role.objects.filter(person__user=self.alice)
        self.assertEqual(roles.count(), 1)
        role = roles.first()
        self.assertEqual(role.organization.lower(), "hastac")
        self.assertEqual(role.affiliation, "member")
        self.assertEqual(role.status, RoleStatus.ACTIVE)

    def test_enrols_user_matched_by_secondary_email(self):
        path = _write_file(["bob.alt@example.test"])
        self._run(path)
        self.assertTrue(
            Role.objects.filter(person__user=self.bob).exists()
        )

    def test_primary_email_match_is_case_insensitive(self):
        path = _write_file(["ALICE@EXAMPLE.TEST"])
        self._run(path)
        self.assertTrue(
            Role.objects.filter(person__user=self.alice).exists()
        )

    def test_unknown_email_creates_no_role(self):
        path = _write_file(["ghost@example.test"])
        self._run(path)
        self.assertEqual(Role.objects.count(), 0)

    def test_blank_lines_are_skipped(self):
        path = _write_file(["", "alice@example.test", "   ", ""])
        self._run(path)
        self.assertEqual(Role.objects.count(), 1)

    def test_idempotent_when_already_enrolled(self):
        path = _write_file(["alice@example.test"])
        self._run(path)
        self._run(path)
        self.assertEqual(
            Role.objects.filter(person__user=self.alice).count(), 1
        )

    def test_dry_run_does_not_write(self):
        path = _write_file(["alice@example.test"])
        self._run(path, "--dry-run")
        self.assertFalse(Role.objects.exists())
        self.assertFalse(Person.objects.filter(user=self.alice).exists())

    def test_refresh_called_for_each_enrolled_profile(self):
        path = _write_file(
            ["alice@example.test", "bob.primary@example.test"]
        )
        with patch(
            "knowledge_commons_profiles.newprofile.society_enrolment."
            "ExternalSync.refresh_local_memberships"
        ) as mock_refresh:
            self._run(path)
        refreshed = {c.args[0].username for c in mock_refresh.call_args_list}
        self.assertEqual(refreshed, {"alice", "bob"})

    def test_refresh_not_called_in_dry_run(self):
        path = _write_file(["alice@example.test"])
        with patch(
            "knowledge_commons_profiles.newprofile.society_enrolment."
            "ExternalSync.refresh_local_memberships"
        ) as mock_refresh:
            self._run(path, "--dry-run")
        mock_refresh.assert_not_called()

    def test_membership_json_reflects_enrolment(self):
        """After running, the profile's is_member_of records HASTAC."""
        path = _write_file(["alice@example.test"])
        self._run(path)
        self.alice.refresh_from_db()
        stored = json.loads(self.alice.is_member_of)
        self.assertTrue(stored["HASTAC"])

    def test_missing_file_raises_command_error(self):
        bogus = str(Path(tempfile.gettempdir()) / "does-not-exist.txt")
        with self.assertRaises(CommandError):
            call_command("enrol_hastac", bogus, stdout=StringIO())

    def test_multiple_matches_skips_user(self):
        Profile.objects.create(
            username="alice2", email="alice@example.test", emails=[]
        )
        path = _write_file(["alice@example.test"])
        self._run(path)
        self.assertEqual(Role.objects.count(), 0)

    def test_makes_no_external_http_calls(self):
        path = _write_file(["alice@example.test"])
        with patch(
            "knowledge_commons_profiles.rest_api.sync.requests.get"
        ) as mock_get:
            self._run(path)
        mock_get.assert_not_called()

    def test_enrolling_in_hastac_does_not_grant_stemedplus(self):
        """Enrolling in HASTAC only flips HASTAC, not STEMED+."""
        path = _write_file(["alice@example.test"])
        self._run(path)
        self.alice.refresh_from_db()
        stored = json.loads(self.alice.is_member_of)
        self.assertTrue(stored["HASTAC"])
        self.assertFalse(stored["STEMED+"])
