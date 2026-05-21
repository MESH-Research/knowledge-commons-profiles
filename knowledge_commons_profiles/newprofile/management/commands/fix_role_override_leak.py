"""
One-off remediation: recompute ``Profile.is_member_of`` for every profile
with a non-empty ``role_overrides`` array.

Background: an earlier version of ``ExternalSync._handle_comanage_roles``
leaked ``role_overrides`` into ``is_member_of``, which made the
``manage_roles`` admin view mis-categorise override-flagged memberships
as API-sourced ("Roles Returned from APIs") instead of manual
("Role Overrides"). The leak is fixed in the current
``_handle_comanage_roles``; this command corrects already-persisted data
by re-running ``ExternalSync.refresh_local_memberships`` for each
affected profile. The corrected ``is_member_of`` reflects API/COmanage
sources only — ``role_overrides`` is untouched and continues to be
merged into the membership API view at read time.

Safe to run multiple times.
"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Recompute Profile.is_member_of for every profile with non-empty "
        "role_overrides so the field reflects API/COmanage sources only. "
        "role_overrides itself is left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        affected = Profile.objects.exclude(role_overrides=[])
        count = affected.count()
        self.stdout.write(
            f"Found {count} profile(s) with non-empty role_overrides"
        )

        refreshed = 0
        errors = 0
        for profile in affected:
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] would refresh {profile.username}"
                )
                refreshed += 1
                continue

            try:
                ExternalSync.refresh_local_memberships(profile)
            except Exception:
                errors += 1
                logger.exception(
                    "Failed to refresh %s", profile.username
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to refresh {profile.username}"
                    )
                )
                continue

            refreshed += 1
            self.stdout.write(f"refreshed {profile.username}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. refreshed={refreshed} errors={errors}"
            )
        )
