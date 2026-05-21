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

from knowledge_commons_profiles.newprofile.models import Profile

SOCIETY_MAPPINGS = {"hastac": "HASTAC", "stemedplus": "STEMED+"}


def _write_file(emails):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(emails))
    return path


@override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
class EnrolHastacTests(TestCase):
    """``enrol_hastac`` flags users via ``Profile.role_overrides``."""

    NOTIFY_TARGET = (
        "knowledge_commons_profiles.newprofile.society_enrolment."
        "ExternalSync.notify_subscribers"
    )

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
        with patch(self.NOTIFY_TARGET):
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

        self.alice.refresh_from_db()
        self.assertIn("HASTAC", self.alice.role_overrides)

    def test_enrols_user_matched_by_secondary_email(self):
        path = _write_file(["bob.alt@example.test"])
        self._run(path)
        self.bob.refresh_from_db()
        self.assertIn("HASTAC", self.bob.role_overrides)

    def test_primary_email_match_is_case_insensitive(self):
        path = _write_file(["ALICE@EXAMPLE.TEST"])
        self._run(path)
        self.alice.refresh_from_db()
        self.assertIn("HASTAC", self.alice.role_overrides)

    def test_unknown_email_leaves_no_overrides(self):
        path = _write_file(["ghost@example.test"])
        self._run(path)
        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.role_overrides, [])
        self.assertEqual(self.bob.role_overrides, [])

    def test_blank_lines_are_skipped(self):
        path = _write_file(["", "alice@example.test", "   ", ""])
        self._run(path)
        flagged = Profile.objects.filter(
            role_overrides__contains=["HASTAC"]
        ).count()
        self.assertEqual(flagged, 1)

    def test_idempotent_when_already_enrolled(self):
        path = _write_file(["alice@example.test"])
        self._run(path)
        self._run(path)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role_overrides.count("HASTAC"), 1)

    def test_dry_run_does_not_write(self):
        path = _write_file(["alice@example.test"])
        self._run(path, "--dry-run")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role_overrides, [])

    def test_refresh_called_for_each_enrolled_profile(self):
        path = _write_file(
            ["alice@example.test", "bob.primary@example.test"]
        )
        with patch(
            "knowledge_commons_profiles.newprofile.society_enrolment."
            "ExternalSync.refresh_local_memberships"
        ) as mock_refresh, patch(self.NOTIFY_TARGET):
            call_command(
                "enrol_hastac",
                path,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        refreshed = {c.args[0].username for c in mock_refresh.call_args_list}
        self.assertEqual(refreshed, {"alice", "bob"})

    def test_refresh_not_called_in_dry_run(self):
        path = _write_file(["alice@example.test"])
        with patch(
            "knowledge_commons_profiles.newprofile.society_enrolment."
            "ExternalSync.refresh_local_memberships"
        ) as mock_refresh, patch(self.NOTIFY_TARGET):
            call_command(
                "enrol_hastac",
                path,
                "--dry-run",
                stdout=StringIO(),
                stderr=StringIO(),
            )
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
        with self.assertRaises(CommandError), patch(self.NOTIFY_TARGET):
            call_command("enrol_hastac", bogus, stdout=StringIO())

    def test_multiple_matches_skips_user(self):
        Profile.objects.create(
            username="alice2", email="alice@example.test", emails=[]
        )
        path = _write_file(["alice@example.test"])
        self._run(path)
        self.assertFalse(
            Profile.objects.filter(
                role_overrides__contains=["HASTAC"]
            ).exists()
        )

    def test_buddypress_is_notified_for_each_enrolled_profile(self):
        """Ping BuddyPress during the import, once per matched profile."""
        path = _write_file(
            ["alice@example.test", "bob.primary@example.test"]
        )
        with patch(self.NOTIFY_TARGET) as mock_notify:
            call_command(
                "enrol_hastac",
                path,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        notified = {c.args[0].username for c in mock_notify.call_args_list}
        self.assertEqual(notified, {"alice", "bob"})

    def test_buddypress_notified_even_when_already_enrolled(self):
        """A re-run pings BP again so BP converges on the right state."""
        path = _write_file(["alice@example.test"])
        self._run(path)  # first run; notify is patched away
        with patch(self.NOTIFY_TARGET) as mock_notify:
            call_command(
                "enrol_hastac",
                path,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        self.assertEqual(mock_notify.call_count, 1)

    def test_buddypress_not_notified_in_dry_run(self):
        path = _write_file(["alice@example.test"])
        with patch(self.NOTIFY_TARGET) as mock_notify:
            call_command(
                "enrol_hastac",
                path,
                "--dry-run",
                stdout=StringIO(),
                stderr=StringIO(),
            )
        mock_notify.assert_not_called()

    def test_webhook_failure_does_not_block_subsequent_profiles(self):
        path = _write_file(
            ["alice@example.test", "bob.primary@example.test"]
        )
        with patch(self.NOTIFY_TARGET) as mock_notify:
            mock_notify.side_effect = [RuntimeError("boom"), None]
            call_command(
                "enrol_hastac",
                path,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertIn("HASTAC", self.alice.role_overrides)
        self.assertIn("HASTAC", self.bob.role_overrides)
        self.assertEqual(mock_notify.call_count, 2)

    def test_enrolling_in_hastac_does_not_grant_stemedplus(self):
        """Enrolling in HASTAC only flips HASTAC, not STEMED+."""
        path = _write_file(["alice@example.test"])
        self._run(path)
        self.alice.refresh_from_db()
        stored = json.loads(self.alice.is_member_of)
        self.assertTrue(stored["HASTAC"])
        self.assertFalse(stored["STEMED+"])
