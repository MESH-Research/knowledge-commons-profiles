"""Seed synthetic identities for load testing.

Creates `Profile`, Django `User`, and `SubAssociation` rows in lockstep so
that the IDMS callback at `cilogon/views.py` finds an existing
SubAssociation for each `loadtest_NNNN` subject and exercises the real
login path (rather than redirecting to /associate/).

Usage:
    LOADTEST=1 ./manage.py seed_loadtest_identities --count 2000
    LOADTEST=1 ./manage.py seed_loadtest_identities --cleanup

Safety: refuses to run unless `LOADTEST=1` is set AND the resolved hostname
is in the allowlist (override via `LOADTEST_HOSTNAME_ALLOWLIST`). The
production hostname is rejected unconditionally.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.newprofile.models import Profile

DEFAULT_COUNT = 2000
DEFAULT_PREFIX = "loadtest_"
DEFAULT_OUTPUT = "/tmp/loadtest_subjects.txt"  # noqa: S108
PRODUCTION_HOSTNAMES = {"profile.hcommons.org", "profile.kcommons.org"}
DEFAULT_ALLOWLIST = {
    "profile.hcommons-test.org",
    "localhost",
    "127.0.0.1",
}


def _resolve_allowlist() -> set[str]:
    raw = os.environ.get("LOADTEST_HOSTNAME_ALLOWLIST", "")
    if not raw:
        return set(DEFAULT_ALLOWLIST)
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _check_safety_or_die() -> None:
    if os.environ.get("LOADTEST") != "1":
        msg = (
            "LOADTEST=1 must be set to run this command. Refusing to seed or "
            "delete identities."
        )
        raise CommandError(msg)

    hostname = (
        os.environ.get("LOADTEST_HOSTNAME_OVERRIDE", "") or socket.getfqdn()
    ).lower()

    if hostname in PRODUCTION_HOSTNAMES:
        msg = (
            f"Refusing to run on production hostname '{hostname}'. This "
            "command never runs against production."
        )
        raise CommandError(msg)

    allowlist = _resolve_allowlist()
    if hostname not in allowlist and not any(
        hostname.endswith(f".{h}") for h in allowlist
    ):
        msg = (
            f"Hostname '{hostname}' is not in the loadtest allowlist "
            f"({sorted(allowlist)}). Set LOADTEST_HOSTNAME_ALLOWLIST or "
            "LOADTEST_HOSTNAME_OVERRIDE to proceed."
        )
        raise CommandError(msg)


class Command(BaseCommand):
    help = "Seed (or clean up) synthetic identities for IDMS load testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help=f"Number of identities to seed (default: {DEFAULT_COUNT}).",
        )
        parser.add_argument(
            "--prefix",
            default=DEFAULT_PREFIX,
            help=f"Prefix for generated usernames (default: {DEFAULT_PREFIX}).",
        )
        parser.add_argument(
            "--output",
            default=DEFAULT_OUTPUT,
            help=(
                "Path to write the subject list, one per line "
                f"(default: {DEFAULT_OUTPUT})."
            ),
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help=(
                "Delete all loadtest_* identities and their related rows "
                "(SubAssociation, TokenUserAgentAssociations, User, Profile)."
            ),
        )

    def handle(self, *args, **options):
        _check_safety_or_die()
        prefix = options["prefix"]
        if options["cleanup"]:
            self._cleanup(prefix)
            return
        self._seed(
            count=options["count"],
            prefix=prefix,
            output_path=options["output"],
        )

    # ------------------------------------------------------------------ seed

    def _seed(self, *, count: int, prefix: str, output_path: str) -> None:
        if count <= 0:
            msg = "--count must be a positive integer."
            raise CommandError(msg)

        width = max(4, len(str(count - 1)))
        subjects: list[str] = []

        for i in range(count):
            sub = f"{prefix}{i:0{width}d}"
            self._seed_one(sub)
            subjects.append(sub)

            if (i + 1) % 500 == 0:
                self.stdout.write(f"  seeded {i + 1}/{count}")

        with Path(output_path).open("w", encoding="utf-8") as fh:
            fh.write("\n".join(subjects) + "\n")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} identities (prefix '{prefix}') -> "
                f"{output_path}"
            )
        )

    def _seed_one(self, sub: str) -> None:
        email = f"{sub}@example.invalid"
        with transaction.atomic():
            profile, _ = Profile.objects.get_or_create(
                username=sub,
                defaults={
                    "name": f"Load Test {sub}",
                    "email": email,
                    "central_user_id": None,
                },
            )
            User.objects.get_or_create(
                username=sub,
                defaults={"email": email},
            )
            SubAssociation.objects.get_or_create(
                sub=sub,
                defaults={
                    "profile": profile,
                    "idp_name": "Mock IdP for Load Testing",
                },
            )

    # --------------------------------------------------------------- cleanup

    def _cleanup(self, prefix: str) -> None:
        sub_qs = SubAssociation.objects.filter(sub__startswith=prefix)
        user_qs = User.objects.filter(username__startswith=prefix)
        profile_qs = Profile.objects.filter(username__startswith=prefix)
        token_qs = TokenUserAgentAssociations.objects.filter(
            user_name__startswith=prefix
        )

        counts = {
            "SubAssociation": sub_qs.count(),
            "TokenUserAgentAssociations": token_qs.count(),
            "User": user_qs.count(),
            "Profile": profile_qs.count(),
        }

        if not any(counts.values()):
            self.stdout.write("Nothing to clean up.")
            return

        with transaction.atomic():
            sub_qs.delete()
            token_qs.delete()
            user_qs.delete()
            profile_qs.delete()

        for model_name, n in counts.items():
            self.stdout.write(f"  deleted {n} {model_name}")
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup done (prefix '{prefix}').")
        )
