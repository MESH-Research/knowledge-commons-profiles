"""Tests for the resolve_username_case_collisions management command."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile

LOAD_ROWS_TARGET = (
    "knowledge_commons_profiles.newprofile.management.commands."
    "resolve_username_case_collisions.load_profile_rows"
)


def _run(*args):
    """Invoke the command, returning its captured stdout."""
    out = StringIO()
    call_command(
        "resolve_username_case_collisions", *args, stdout=out, stderr=out
    )
    return out.getvalue()


class ResolveUsernameCaseCollisionsTests(TestCase):
    """The command reports and resolves case-insensitive username clashes."""

    def test_clean_database_reports_no_collisions(self):
        Profile.objects.create(username="alice", name="Alice")
        Profile.objects.create(username="bob", name="Bob")

        output = _run()

        self.assertIn("No case-insensitive username collisions", output)

    def test_dry_run_reports_collisions_without_persisting(self):
        kept = Profile.objects.create(username="alice", name="Alice")
        other = Profile.objects.create(username="placeholder_b", name="B")

        with patch(
            LOAD_ROWS_TARGET,
            return_value=[(kept.id, "alice"), (other.id, "Alice")],
        ):
            output = _run()

        # Report names both profiles and the proposed rename.
        self.assertIn(str(kept.id), output)
        self.assertIn(str(other.id), output)
        self.assertIn("Alice_1", output)
        self.assertIn("--apply", output)

        # Nothing was written.
        other.refresh_from_db()
        self.assertEqual(other.username, "placeholder_b")

    def test_apply_persists_renames(self):
        kept = Profile.objects.create(username="alice", name="Alice")
        other = Profile.objects.create(username="placeholder_b", name="B")

        with patch(
            LOAD_ROWS_TARGET,
            return_value=[(kept.id, "alice"), (other.id, "Alice")],
        ):
            _run("--apply")

        kept.refresh_from_db()
        other.refresh_from_db()
        # Oldest keeps its username; the other is suffixed.
        self.assertEqual(kept.username, "alice")
        self.assertEqual(other.username, "Alice_1")

    def test_apply_is_idempotent(self):
        kept = Profile.objects.create(username="alice", name="Alice")
        other = Profile.objects.create(username="placeholder_b", name="B")

        with patch(
            LOAD_ROWS_TARGET,
            return_value=[(kept.id, "alice"), (other.id, "Alice")],
        ):
            _run("--apply")

        # A second run against the now-clean data finds nothing to do.
        output = _run("--apply")
        self.assertIn("No case-insensitive username collisions", output)

    def test_report_lists_every_id_and_old_to_new_rename(self):
        oldest = Profile.objects.create(username="alice", name="A1")
        mid = Profile.objects.create(username="placeholder_m", name="A2")
        newest = Profile.objects.create(username="placeholder_n", name="A3")

        rows = [
            (oldest.id, "alice"),
            (mid.id, "Alice"),
            (newest.id, "ALICE"),
        ]
        with patch(LOAD_ROWS_TARGET, return_value=rows):
            output = _run()

        for profile in (oldest, mid, newest):
            self.assertIn(str(profile.id), output)
        self.assertIn("Alice_1", output)
        self.assertIn("ALICE_2", output)

    def test_apply_resolves_three_way_collision_keeping_oldest(self):
        oldest = Profile.objects.create(username="alice", name="A1")
        mid = Profile.objects.create(username="placeholder_m", name="A2")
        newest = Profile.objects.create(username="placeholder_n", name="A3")

        rows = [
            (oldest.id, "alice"),
            (mid.id, "Alice"),
            (newest.id, "ALICE"),
        ]
        with patch(LOAD_ROWS_TARGET, return_value=rows):
            _run("--apply")

        oldest.refresh_from_db()
        mid.refresh_from_db()
        newest.refresh_from_db()
        self.assertEqual(oldest.username, "alice")
        self.assertEqual(mid.username, "Alice_1")
        self.assertEqual(newest.username, "ALICE_2")
