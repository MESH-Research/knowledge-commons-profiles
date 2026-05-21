"""
Shared logic for bulk-enrolling users on a society from a list of emails.

Used by the per-society management commands (``enrol_stemedplus``,
``enrol_hastac``). Reading a flat file of email addresses, matching them
to ``Profile`` rows, writing the corresponding ``Role``, and refreshing
``Profile.is_member_of`` are all the same regardless of which society
the run targets — only a handful of identifying strings differ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

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


ROLE_AFFILIATION = "member"
ROLE_SOURCE_SYSTEM = "manual-enrolment"


@dataclass(frozen=True)
class SocietySpec:
    """Identifying values for a society used by the enrolment helper."""

    slug: str
    name: str
    role_organization: str


def read_emails(path: Path) -> list[str]:
    emails = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        email = raw.strip()
        if email:
            emails.append(email)
    return emails


def find_profiles(email: str) -> list[Profile]:
    return list(
        Profile.objects.filter(
            Q(email__iexact=email) | Q(emails__contains=[email])
        ).distinct()
    )


def enrol_from_file(
    spec: SocietySpec,
    file_path: str,
    stdout,
    style,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run a bulk enrolment from an email file. Returns counts."""
    path = Path(file_path)
    if not path.exists():
        msg = f"File not found: {path}"
        raise CommandError(msg)

    emails = read_emails(path)
    if not emails:
        stdout.write(style.WARNING("No emails in file."))
        return {
            "enrolled": 0,
            "already": 0,
            "missing": 0,
            "multiple": 0,
            "errors": 0,
        }

    counts = {
        "enrolled": 0,
        "already": 0,
        "missing": 0,
        "multiple": 0,
        "errors": 0,
    }

    ctx = transaction.atomic() if not dry_run else _NullContext()
    with ctx:
        co = _get_co(spec, dry_run=dry_run)
        for email in emails:
            _process_email(
                spec, email, co, stdout, style, counts, dry_run=dry_run
            )

    stdout.write(
        style.SUCCESS(
            "Done. "
            f"enrolled={counts['enrolled']} "
            f"already={counts['already']} "
            f"missing={counts['missing']} "
            f"multiple={counts['multiple']} "
            f"errors={counts['errors']}"
        )
    )
    return counts


def _get_co(spec: SocietySpec, *, dry_run: bool) -> CO:
    if dry_run:
        return CO(slug=spec.slug, name=spec.name)
    co, _ = CO.objects.get_or_create(slug=spec.slug, name=spec.name)
    return co


# ruff: noqa: PLR0913
def _process_email(
    spec: SocietySpec,
    email: str,
    co: CO,
    stdout,
    style,
    counts: dict[str, int],
    *,
    dry_run: bool,
) -> None:
    profiles = find_profiles(email)
    if not profiles:
        stdout.write(f"NOT FOUND: {email}")
        counts["missing"] += 1
        return
    if len(profiles) > 1:
        stdout.write(
            style.WARNING(f"MULTIPLE MATCHES for {email}: skipping")
        )
        counts["multiple"] += 1
        return

    profile = profiles[0]

    if dry_run:
        stdout.write(
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
            defaults={"organization": spec.role_organization},
        )
    except Exception:
        counts["errors"] += 1
        logger.exception(
            "Failed to enrol %s (%s)", profile.username, email
        )
        return

    if created:
        counts["enrolled"] += 1
        stdout.write(f"ENROLLED: {profile.username} ({email})")
    else:
        counts["already"] += 1
        stdout.write(f"ALREADY ENROLLED: {profile.username} ({email})")

    try:
        ExternalSync.refresh_local_memberships(profile)
    except Exception:
        logger.exception(
            "Failed to refresh memberships for %s", profile.username
        )


class _NullContext:
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, tb): ...
