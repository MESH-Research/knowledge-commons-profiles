"""
Normalise stored email addresses to lowercase.

Walks every :class:`Profile`, lowercases the primary ``email`` and every
entry of the ``emails`` ArrayField (dedupes the latter), and updates the
linked Django :class:`User.email` to match. Idempotent and safe to re-run.

Usage::

    uv run ./manage.py normalise_emails [--dry-run]
"""

import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge_commons_profiles.common.profiles_email import normalize_email
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Lowercase Profile.email and every entry in Profile.emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        profiles_changed = 0
        users_changed = 0
        collisions = 0

        for profile in Profile.objects.all().iterator():
            new_email = normalize_email(profile.email) or ""
            normalised_secondaries = sorted(
                {
                    normalize_email(e)
                    for e in (profile.emails or [])
                    if normalize_email(e)
                }
            )

            primary_changed = new_email != profile.email
            secondaries_changed = normalised_secondaries != list(
                profile.emails or []
            )

            if not primary_changed and not secondaries_changed:
                continue

            # Detect a collision between the new primary and another profile.
            # We still proceed (the field has no uniqueness constraint), but
            # we surface it so admins can reconcile.
            if new_email and primary_changed:
                colliding = (
                    Profile.objects.filter(email=new_email)
                    .exclude(pk=profile.pk)
                    .exists()
                )
                if colliding:
                    collisions += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Collision: profile {profile.pk} "
                            f"({profile.username}) normalises to "
                            f"{new_email}, which is already used by "
                            f"another profile."
                        )
                    )

            if dry_run:
                profiles_changed += 1
                self.stdout.write(
                    f"[DRY-RUN] would update {profile.username}: "
                    f"email={profile.email!r} -> {new_email!r}, "
                    f"emails={profile.emails!r} -> "
                    f"{normalised_secondaries!r}"
                )
                continue

            with transaction.atomic():
                profile.email = new_email
                profile.emails = normalised_secondaries
                profile.save(update_fields=["email", "emails"])
                profiles_changed += 1

                # Keep the matching Django auth User in sync.
                user_qs = User.objects.filter(username=profile.username)
                for user in user_qs:
                    canonical = normalize_email(user.email) or ""
                    if canonical != user.email:
                        user.email = canonical
                        user.save(update_fields=["email"])
                        users_changed += 1

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {profiles_changed} profile(s); "
                f"{users_changed} user(s); "
                f"{collisions} collision(s) detected."
            )
        )
