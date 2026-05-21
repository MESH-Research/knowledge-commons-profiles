"""
Bulk-enrol users on STEMEd+ from a file of email addresses.

One email per line; blank lines ignored. For each matched profile the
command creates a STEMEd+ Role and refreshes Profile.is_member_of so
the change surfaces in the UI immediately. The refresh path is local
only; no external HTTP is made.
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q

from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)


STEMEDPLUS_SLUG = "stemedplus"
STEMEDPLUS_NAME = "STEMEDPLUS"
ROLE_ORGANIZATION = "Stemedplus"
ROLE_AFFILIATION = "member"
ROLE_SOURCE_SYSTEM = "manual-enrolment"


def _read_emails(path: Path) -> list[str]:
    emails = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        email = raw.strip()
        if email:
            emails.append(email)
    return emails


def _find_profiles(email: str) -> list[Profile]:
    return list(
        Profile.objects.filter(
            Q(email__iexact=email) | Q(emails__contains=[email])
        ).distinct()
    )


class Command(BaseCommand):
    help = (
        "Enrol the users associated with the email addresses in the given "
        "file on STEMEd+. One email per line; blank lines ignored."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="Path to a file containing one email address per line.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report matches without writing to the database.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            msg = f"File not found: {path}"
            raise CommandError(msg)

        dry_run: bool = options["dry_run"]
        emails = _read_emails(path)

        if not emails:
            self.stdout.write(self.style.WARNING("No emails in file."))
            return

        counts = {
            "enrolled": 0,
            "already": 0,
            "missing": 0,
            "multiple": 0,
            "errors": 0,
        }

        ctx = transaction.atomic() if not dry_run else _NullContext()
        with ctx:
            co = self._get_co(dry_run=dry_run)
            for email in emails:
                self._process_email(email, co, counts, dry_run=dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"enrolled={counts['enrolled']} "
                f"already={counts['already']} "
                f"missing={counts['missing']} "
                f"multiple={counts['multiple']} "
                f"errors={counts['errors']}"
            )
        )

    def _get_co(self, *, dry_run: bool) -> CO:
        if dry_run:
            return CO(slug=STEMEDPLUS_SLUG, name=STEMEDPLUS_NAME)
        co, _ = CO.objects.get_or_create(
            slug=STEMEDPLUS_SLUG,
            name=STEMEDPLUS_NAME,
        )
        return co

    # ruff: noqa: PLR0913
    def _process_email(
        self,
        email: str,
        co: CO,
        counts: dict[str, int],
        *,
        dry_run: bool,
    ) -> None:
        profiles = _find_profiles(email)
        if not profiles:
            self.stdout.write(f"NOT FOUND: {email}")
            counts["missing"] += 1
            return
        if len(profiles) > 1:
            self.stdout.write(
                self.style.WARNING(
                    f"MULTIPLE MATCHES for {email}: skipping"
                )
            )
            counts["multiple"] += 1
            return

        profile = profiles[0]

        if dry_run:
            self.stdout.write(
                f"[DRY-RUN] would enrol {profile.username} ({email})"
            )
            counts["enrolled"] += 1
            return

        try:
            person, _ = Person.objects.get_or_create(user=profile)
            _, created = Role.objects.get_or_create(
                person=person,
                co=co,
                cou=None,
                affiliation=ROLE_AFFILIATION,
                status=RoleStatus.ACTIVE,
                source_system=ROLE_SOURCE_SYSTEM,
                defaults={"organization": ROLE_ORGANIZATION},
            )
        except Exception:
            counts["errors"] += 1
            logger.exception(
                "Failed to enrol %s (%s)", profile.username, email
            )
            return

        if created:
            counts["enrolled"] += 1
            self.stdout.write(
                f"ENROLLED: {profile.username} ({email})"
            )
        else:
            counts["already"] += 1
            self.stdout.write(
                f"ALREADY ENROLLED: {profile.username} ({email})"
            )

        try:
            ExternalSync.refresh_local_memberships(profile)
        except Exception:
            logger.exception(
                "Failed to refresh memberships for %s", profile.username
            )


class _NullContext:
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, tb): ...
