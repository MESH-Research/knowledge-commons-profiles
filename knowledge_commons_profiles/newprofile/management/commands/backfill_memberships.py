"""
Backfill Profile.is_member_of for profiles that have never been synced.

Network membership listings read the materialized ``is_member_of`` JSON,
which is only written when a profile passes through ExternalSync — login,
a REST profile fetch, enrolment, or an import_comanage run. Members who
have never triggered any of those have ``is_member_of`` NULL and are
invisible to /network/<name>/members/ even when local Role rows (or
external partner APIs) say they are members.

By default this command refreshes the local COmanage-derived societies
(settings.KNOWN_SOCIETY_MAPPINGS) from Role rows only — no external API
calls. With ``--full`` it runs the complete ExternalSync.sync per
profile, including the external partner APIs (MLA, MSU, ARLISNA, UP).

Subscribers (settings.WEBHOOK_URLS) are notified once per profile whose
memberships actually changed, so downstream services re-fetch; suppress
with --no-notify.
"""

import json
import logging
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Q

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)

# is_member_of values that count as "never synced" for --missing-only
MISSING_VALUES = ("", "{}")


class Command(BaseCommand):
    """
    Materialize is_member_of for profiles missing sync data.
    """

    help = (
        "Backfill Profile.is_member_of so network membership listings "
        "include members who have never been synced. Local Role rows "
        "only by default; --full also queries external partner APIs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--full",
            action="store_true",
            help=(
                "Run the complete ExternalSync.sync per profile, "
                "including external partner APIs (MLA, MSU, ARLISNA, "
                "UP). Default is a local-only refresh of the COmanage "
                "societies from Role rows."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "With --full: ignore the SYNC_HOURS cache and re-sync "
                "profiles even if they synced recently."
            ),
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help=(
                "Only process profiles with no sync data at all "
                "(is_member_of NULL or empty)."
            ),
        )
        parser.add_argument(
            "--username",
            help="Process a single profile by username.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help=(
                "Seconds to pause between profiles (rate-limits "
                "external API calls in --full mode)."
            ),
        )
        parser.add_argument(
            "--no-notify",
            action="store_true",
            help=(
                "Do not ping WEBHOOK_URLS for profiles whose "
                "memberships changed."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report which profiles would be processed, write nothing.",
        )
        parser.add_argument(
            "--state-file",
            help=(
                "Record each successfully processed username in this "
                "file and skip recorded usernames on re-run, so an "
                "interrupted run can resume where it stopped. Failed "
                "profiles are not recorded and retry on resume."
            ),
        )

    @staticmethod
    def _parse(value):
        try:
            return json.loads(value) if value else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _build_queryset(options):
        qs = Profile.objects.all().order_by("username")

        if options["username"]:
            qs = qs.filter(username=options["username"])

        if options["missing_only"]:
            qs = qs.filter(
                Q(is_member_of__isnull=True)
                | Q(is_member_of__in=MISSING_VALUES)
            )

        return qs

    @staticmethod
    def _open_state(options):
        """
        Load the set of already-processed usernames and (unless dry-run)
        an append handle for recording new ones.
        """
        if not options["state_file"]:
            return set(), None

        state_path = Path(options["state_file"])
        done = (
            set(state_path.read_text().split())
            if state_path.exists()
            else set()
        )

        if options["dry_run"]:
            return done, None

        return done, state_path.open("a")

    def _backfill_profile(self, profile, options) -> bool:
        """
        Backfill one profile; return True if its memberships changed.
        """
        before = self._parse(profile.is_member_of)

        if options["full"]:
            ExternalSync.sync(
                profile=profile,
                cache=not options["force"],
                webhooks=False,
            )
        else:
            ExternalSync.refresh_local_memberships(profile)

        return self._parse(profile.is_member_of) != before

    def handle(self, *args, **options):
        counts = dict.fromkeys(
            ("processed", "changed", "notified", "skipped", "errors"), 0
        )
        done, state_handle = self._open_state(options)

        try:
            for profile in self._build_queryset(options).iterator():
                if profile.username in done:
                    counts["skipped"] += 1
                    continue

                if options["dry_run"]:
                    self.stdout.write(
                        f"[DRY-RUN] would backfill {profile.username}"
                    )
                    counts["processed"] += 1
                    continue

                try:
                    has_changed = self._backfill_profile(profile, options)
                except Exception:
                    counts["errors"] += 1
                    logger.exception(
                        "Failed to backfill memberships for %s",
                        profile.username,
                    )
                    self.stderr.write(
                        self.style.ERROR(f"Failed: {profile.username}")
                    )
                    continue

                counts["processed"] += 1

                if has_changed:
                    counts["changed"] += 1
                    if not options["no_notify"]:
                        ExternalSync.notify_subscribers(profile)
                        counts["notified"] += 1

                # record only after the profile is fully handled so an
                # interrupted run retries anything in flight
                if state_handle:
                    state_handle.write(f"{profile.username}\n")
                    state_handle.flush()

                if options["sleep"]:
                    time.sleep(options["sleep"])
        finally:
            if state_handle:
                state_handle.close()

        self.stdout.write(
            self.style.SUCCESS(
                "Processed {processed} profile(s): {changed} changed, "
                "{notified} notified, {skipped} skipped, "
                "{errors} error(s)".format(**counts)
            )
        )
