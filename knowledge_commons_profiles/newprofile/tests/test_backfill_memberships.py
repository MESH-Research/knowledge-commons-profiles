"""
Tests for the backfill_memberships management command.

The command materializes Profile.is_member_of for profiles that have
never been synced, so network membership listings include them. Local
mode recomputes the KNOWN_SOCIETY_MAPPINGS societies from real Role
rows; --full delegates to ExternalSync.sync (mocked here — it calls
external partner APIs). Webhook notifications are mocked: they are
outbound HTTP.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus
from knowledge_commons_profiles.rest_api.sync import ExternalSync

User = get_user_model()

SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}


@override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
class BackfillMembershipsTests(TestCase):
    def setUp(self):
        self.co = CO.objects.create(id=18, name="STEMEDPLUS", slug="stemedplus")

    def _profile_with_role(self, username, organization="stemedplus"):
        profile = Profile.objects.create(username=username)
        person = Person.objects.create(display_name=username, user=profile)
        Role.objects.create(
            person=person,
            co=self.co,
            affiliation="member",
            status=RoleStatus.ACTIVE,
            organization=organization,
            source_system="co-manage",
        )
        return profile

    def _call(self, *args):
        out = StringIO()
        with patch(
            "knowledge_commons_profiles.rest_api.sync."
            "ExternalSync.notify_subscribers"
        ) as notify:
            call_command("backfill_memberships", *args, stdout=out)
        return out.getvalue(), notify

    def _memberships(self, profile):
        profile.refresh_from_db()
        return json.loads(profile.is_member_of or "{}")

    def test_materializes_memberships_for_never_synced_profile(self):
        profile = self._profile_with_role("bonnie")
        self.assertIsNone(profile.is_member_of)

        self._call()

        self.assertEqual(
            self._memberships(profile),
            {"STEMED+": True, "HASTAC": False},
        )

    def test_corrects_stale_memberships_by_default(self):
        profile = self._profile_with_role("bonnie")
        profile.is_member_of = json.dumps(
            {"STEMED+": False, "HASTAC": False, "MLA": True}
        )
        profile.save()

        self._call()

        # mapped societies recomputed from Role rows; non-COmanage keys
        # (MLA) preserved
        self.assertEqual(
            self._memberships(profile),
            {"STEMED+": True, "HASTAC": False, "MLA": True},
        )

    def test_missing_only_skips_profiles_with_sync_data(self):
        stale = self._profile_with_role("bonnie")
        stale.is_member_of = json.dumps({"STEMED+": False})
        stale.save()
        never_synced = self._profile_with_role("clyde")

        self._call("--missing-only")

        # stale profile untouched, never-synced profile materialized
        self.assertEqual(self._memberships(stale), {"STEMED+": False})
        self.assertTrue(self._memberships(never_synced)["STEMED+"])

    def test_username_limits_to_one_profile(self):
        target = self._profile_with_role("bonnie")
        other = self._profile_with_role("clyde")

        self._call("--username", "bonnie")

        self.assertTrue(self._memberships(target)["STEMED+"])
        self.assertEqual(self._memberships(other), {})

    def test_notifies_subscribers_only_for_changed_profiles(self):
        changed = self._profile_with_role("bonnie")
        unchanged = Profile.objects.create(
            username="clyde",
            is_member_of=json.dumps({"STEMED+": False, "HASTAC": False}),
        )

        _, notify = self._call()

        notified = {
            call.args[0].username for call in notify.call_args_list
        }
        self.assertIn(changed.username, notified)
        self.assertNotIn(unchanged.username, notified)

    def test_no_notify_suppresses_webhooks(self):
        self._profile_with_role("bonnie")

        _, notify = self._call("--no-notify")

        notify.assert_not_called()

    def test_dry_run_writes_nothing_and_notifies_nobody(self):
        profile = self._profile_with_role("bonnie")

        out, notify = self._call("--dry-run")

        profile.refresh_from_db()
        self.assertIsNone(profile.is_member_of)
        notify.assert_not_called()
        self.assertIn("bonnie", out)

    def test_error_on_one_profile_does_not_abort_the_run(self):
        self._profile_with_role("bonnie")
        survivor = self._profile_with_role("clyde")

        real_refresh = (
            "knowledge_commons_profiles.rest_api.sync."
            "ExternalSync.refresh_local_memberships"
        )
        original = ExternalSync.refresh_local_memberships

        def flaky(profile):
            if profile.username == "bonnie":
                msg = "boom"
                raise RuntimeError(msg)
            return original(profile)

        with patch(real_refresh, side_effect=flaky):
            self._call("--no-notify")

        self.assertTrue(self._memberships(survivor)["STEMED+"])

    def _state_file(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(
            lambda: __import__("shutil").rmtree(tmpdir, ignore_errors=True)
        )
        return Path(tmpdir) / "state.txt"

    def test_state_file_records_processed_profiles(self):
        self._profile_with_role("bonnie")
        self._profile_with_role("clyde")
        state = self._state_file()

        self._call("--state-file", str(state))

        self.assertEqual(
            state.read_text().split(), ["bonnie", "clyde"]
        )

    def test_state_file_resumes_by_skipping_processed_profiles(self):
        skipped = self._profile_with_role("bonnie")
        fresh = self._profile_with_role("clyde")
        state = self._state_file()
        state.write_text("bonnie\n")

        self._call("--state-file", str(state))

        # bonnie was recorded as done, so she is untouched on resume
        self.assertEqual(self._memberships(skipped), {})
        self.assertTrue(self._memberships(fresh)["STEMED+"])

    def test_state_file_omits_failed_profiles_so_they_retry(self):
        self._profile_with_role("bonnie")
        self._profile_with_role("clyde")
        state = self._state_file()

        real_refresh = (
            "knowledge_commons_profiles.rest_api.sync."
            "ExternalSync.refresh_local_memberships"
        )
        original = ExternalSync.refresh_local_memberships

        def flaky(profile):
            if profile.username == "bonnie":
                msg = "boom"
                raise RuntimeError(msg)
            return original(profile)

        with patch(real_refresh, side_effect=flaky):
            self._call("--state-file", str(state), "--no-notify")

        # the failure is not recorded; the success is
        self.assertEqual(state.read_text().split(), ["clyde"])

        # second run (no flake) picks bonnie up and completes the state
        bonnie = Profile.objects.get(username="bonnie")
        self._call("--state-file", str(state))
        self.assertTrue(self._memberships(bonnie)["STEMED+"])
        self.assertEqual(
            sorted(state.read_text().split()), ["bonnie", "clyde"]
        )

    def test_dry_run_does_not_write_state_file(self):
        self._profile_with_role("bonnie")
        state = self._state_file()

        self._call("--dry-run", "--state-file", str(state))

        self.assertFalse(state.exists())

    def test_full_mode_runs_external_sync_per_profile(self):
        self._profile_with_role("bonnie")
        self._profile_with_role("clyde")

        with patch(
            "knowledge_commons_profiles.rest_api.sync.ExternalSync.sync"
        ) as sync:
            call_command("backfill_memberships", "--full", stdout=StringIO())

        synced = {
            call.kwargs["profile"].username
            for call in sync.call_args_list
        }
        self.assertEqual(synced, {"bonnie", "clyde"})
        # cache respected by default: profiles synced within SYNC_HOURS
        # are skipped inside sync itself
        self.assertTrue(
            all(call.kwargs["cache"] for call in sync.call_args_list)
        )

    def test_full_mode_force_disables_sync_cache(self):
        self._profile_with_role("bonnie")

        with patch(
            "knowledge_commons_profiles.rest_api.sync.ExternalSync.sync"
        ) as sync:
            call_command(
                "backfill_memberships",
                "--full",
                "--force",
                stdout=StringIO(),
            )

        self.assertFalse(
            any(call.kwargs["cache"] for call in sync.call_args_list)
        )
