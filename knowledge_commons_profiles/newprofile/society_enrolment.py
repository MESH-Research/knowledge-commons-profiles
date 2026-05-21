"""
Shared logic for bulk-enrolling users on a society from a list of emails.

Used by the per-society management commands (``enrol_stemedplus``,
``enrol_hastac``). Reading a flat file of email addresses, matching them
to ``Profile`` rows, writing the society identifier onto
``Profile.role_overrides``, refreshing ``Profile.is_member_of`` and
pinging BuddyPress are all the same regardless of which society the run
targets — only the identifier differs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q

from knowledge_commons_profiles.common.profiles_email import normalize_email
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SocietySpec:
    """
    Identifying value for a society used by the enrolment helper.

    ``name`` is the string written to ``Profile.role_overrides`` and the
    key under which the society appears in ``Profile.is_member_of`` —
    e.g. ``"HASTAC"``, ``"STEMED+"``.
    """

    name: str


def read_emails(path: Path) -> list[str]:
    emails = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        email = normalize_email(raw)
        if email:
            emails.append(email)
    return emails


def find_profiles(email: str) -> list[Profile]:
    email = normalize_email(email) or ""
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
        for email in emails:
            _process_email(spec, email, stdout, style, counts, dry_run=dry_run)

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


# ruff: noqa: PLR0913
def _process_email(
    spec: SocietySpec,
    email: str,
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
            f"[DRY-RUN] would enrol {profile.username} ({email}) "
            f"in {spec.name}"
        )
        counts["enrolled"] += 1
        return

    overrides = list(profile.role_overrides or [])
    if spec.name in overrides:
        counts["already"] += 1
        stdout.write(f"ALREADY ENROLLED: {profile.username} ({email})")
    else:
        profile.role_overrides = sorted({*overrides, spec.name})
        profile.save(update_fields=["role_overrides"])
        counts["enrolled"] += 1
        stdout.write(f"ENROLLED: {profile.username} ({email})")

    # Update the cached membership JSON locally...
    try:
        ExternalSync.refresh_local_memberships(profile)
    except Exception:
        logger.exception(
            "Failed to refresh memberships for %s", profile.username
        )

    # ...then ping BuddyPress ourselves. The bulk command MUST fire this
    # — relying on a later passive sync would leave BP out of date until
    # the user's next session. Wrapped in its own try/except so a
    # webhook failure for one profile does not abort the rest.
    try:
        ExternalSync.notify_subscribers(profile)
    except Exception:
        logger.exception(
            "Failed to notify subscribers for %s", profile.username
        )


class _NullContext:
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, tb): ...
