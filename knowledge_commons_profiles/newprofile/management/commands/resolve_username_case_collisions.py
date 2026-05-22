"""
Find and resolve case-insensitive ``Profile.username`` collisions.

Usage:
    # Report collisions only (no changes)
    ./manage.py resolve_username_case_collisions

    # Persist the renames
    ./manage.py resolve_username_case_collisions --apply

For each group of usernames that are equal once lower-cased, the oldest
profile (lowest id) keeps its username and the rest are renamed with a numeric
suffix (e.g. ``Alice`` -> ``Alice_1``). This must be run before the
``username`` column is converted to the case-insensitive ``citext`` type.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.username_collisions import (
    find_collision_groups,
)
from knowledge_commons_profiles.newprofile.username_collisions import (
    plan_renames,
)


def load_profile_rows():
    """Return ``[(id, username), ...]`` for every profile, ordered by id.

    Isolated as a function so tests can supply collision scenarios that the
    case-insensitive database constraint would otherwise forbid.
    """
    return list(
        Profile.objects.values_list("id", "username").order_by("id")
    )


class Command(BaseCommand):
    help = (
        "Find and resolve case-insensitive Profile.username collisions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Persist the renames. Without this flag the command only "
                "reports what it would do."
            ),
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        rows = load_profile_rows()
        groups = find_collision_groups(rows)

        if not groups:
            self.stdout.write(
                self.style.SUCCESS(
                    "No case-insensitive username collisions found."
                )
            )
            return

        renames = plan_renames(rows)
        new_by_id = {
            profile_id: new for profile_id, _old, new in renames
        }
        self._write_report(groups, new_by_id)

        if not apply_changes:
            self.stdout.write("Run with --apply to perform the renames.")
            return

        with transaction.atomic():
            for profile_id, _old, new in renames:
                Profile.objects.filter(pk=profile_id).update(username=new)

        self.stdout.write(
            self.style.SUCCESS(
                f"Renamed {len(renames)} profile(s) across "
                f"{len(groups)} collision group(s)."
            )
        )

    def _write_report(self, groups, new_by_id):
        """Print each collision group, its Profile IDs, and the renames."""
        self.stdout.write(
            self.style.WARNING(
                f"Found {len(groups)} case-insensitive username "
                f"collision group(s):\n"
            )
        )

        for key in sorted(groups):
            members = groups[key]
            ids = ", ".join(str(profile_id) for profile_id, _u in members)
            self.stdout.write(
                f"  Duplicate username '{key}' (Profile IDs: {ids})"
            )

            for profile_id, username in members:
                new = new_by_id.get(profile_id)
                if new is None:
                    self.stdout.write(
                        f"    KEEP   id={profile_id} "
                        f"username={username!r} (oldest)"
                    )
                else:
                    self.stdout.write(
                        f"    RENAME id={profile_id} "
                        f"{username!r} -> {new!r}"
                    )
            self.stdout.write("")

        self.stdout.write(
            f"Summary: {len(new_by_id)} profile(s) to rename across "
            f"{len(groups)} collision group(s).\n"
        )
