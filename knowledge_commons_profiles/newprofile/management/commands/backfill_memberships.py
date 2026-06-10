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
import signal
import time
from pathlib import Path

import smart_open
from django.core.management.base import BaseCommand
from django.db.models import Q

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)

# is_member_of values that count as "never synced" for --missing-only
MISSING_VALUES = ("", "{}")


class _LocalStateStore:
    """
    Resume state in a local file, appended and flushed per record.
    """

    def __init__(self, path):
        self._path = Path(path)
        self._handle = None

    def load(self) -> set[str]:
        if self._path.exists():
            return set(self._path.read_text().split())
        return set()

    def record(self, username: str) -> None:
        if self._handle is None:
            self._handle = self._path.open("a")
        self._handle.write(f"{username}\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle:
            self._handle.close()


class _RemoteStateStore:
    """
    Resume state in an object store (e.g. s3://) via smart_open.

    Object stores cannot append, so the whole state object is rewritten
    on the first record (so the object appears immediately and access
    problems surface at profile 1), every ``checkpoint_every`` records
    thereafter, and once more on close. A hard kill therefore loses at
    most ``checkpoint_every - 1`` records of progress; those profiles
    are simply re-processed on resume.
    """

    def __init__(self, uri: str, checkpoint_every: int, announce=None):
        self._uri = uri
        self._every = max(1, checkpoint_every)
        self._announce = announce
        self._done: set[str] = set()
        self._unflushed = 0
        self._primed = False

    def load(self) -> set[str]:
        try:
            with smart_open.open(self._uri) as handle:
                self._done = set(handle.read().split())
        except OSError:
            logger.warning(
                "No readable state at %s; starting fresh", self._uri
            )
            self._done = set()
        return set(self._done)

    def record(self, username: str) -> None:
        self._done.add(username)
        self._unflushed += 1
        if not self._primed or self._unflushed >= self._every:
            self._flush()

    def _flush(self) -> None:
        content = "".join(f"{name}\n" for name in sorted(self._done))
        with smart_open.open(self._uri, "w") as handle:
            handle.write(content)
        self._primed = True
        self._unflushed = 0
        if self._announce:
            self._announce(
                f"checkpoint: {len(self._done)} username(s) -> {self._uri}"
            )

    def close(self) -> None:
        if self._unflushed:
            self._flush()


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
                "Record each successfully processed username here and "
                "skip recorded usernames on re-run, so an interrupted "
                "run can resume where it stopped. Accepts a local path "
                "or a smart-open URI (e.g. s3://bucket/key) so state "
                "survives ephemeral containers. Failed profiles are "
                "not recorded and retry on resume."
            ),
        )
        parser.add_argument(
            "--checkpoint-every",
            type=int,
            default=25,
            help=(
                "For remote state (s3:// etc., which cannot append): "
                "rewrite the state object every N processed profiles. "
                "A crash loses at most N-1 profiles of progress."
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

    def _make_store(self, options):
        """
        Build the resume-state store for --state-file, if requested.
        """
        target = options["state_file"]
        if not target:
            return None
        if "://" in target:
            return _RemoteStateStore(
                target,
                options["checkpoint_every"],
                announce=self.stdout.write,
            )
        return _LocalStateStore(target)

    @staticmethod
    def _exit_on_sigterm(signum, frame):
        # container stops deliver SIGTERM; raise so the finally block
        # persists resume state before the process dies
        raise SystemExit(143)

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
        state_store = self._make_store(options)
        done = state_store.load() if state_store else set()

        previous_sigterm = signal.signal(
            signal.SIGTERM, self._exit_on_sigterm
        )

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
                if state_store:
                    state_store.record(profile.username)

                if options["sleep"]:
                    time.sleep(options["sleep"])
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
            if state_store:
                state_store.close()

        self.stdout.write(
            self.style.SUCCESS(
                "Processed {processed} profile(s): {changed} changed, "
                "{notified} notified, {skipped} skipped, "
                "{errors} error(s)".format(**counts)
            )
        )
