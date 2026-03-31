"""
Audit and optionally deduplicate Profile records with the same username.

Usage:
    # Show duplicates (dry run, no changes)
    ./manage.py audit_duplicate_profiles

    # Show what would be deleted, with field details
    ./manage.py audit_duplicate_profiles --verbose

    # Actually delete duplicates (keeps most complete record)
    ./manage.py audit_duplicate_profiles --delete
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from knowledge_commons_profiles.newprofile.models import Profile

FIELDS_TO_CHECK = [
    "name",
    "title",
    "affiliation",
    "email",
    "orcid",
    "twitter",
    "github",
    "mastodon",
]


def _completeness(profile):
    """Count how many key fields have non-empty values."""
    return sum(
        1 for f in FIELDS_TO_CHECK if getattr(profile, f, None)
    )


def _rank_profiles(profiles):
    """Sort profiles by completeness (desc), then id (asc)."""
    return sorted(profiles, key=lambda p: (-_completeness(p), p.id))


def _get_duplicate_groups():
    """Return queryset of usernames with more than one profile."""
    return (
        Profile.objects.values("username")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .order_by("-count")
    )


class Command(BaseCommand):
    help = "Audit duplicate Profile usernames and optionally deduplicate."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete duplicates (keeps most complete).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show field values for each duplicate profile.",
        )

    def handle(self, *args, **options):
        dupes = _get_duplicate_groups()

        if not dupes.exists():
            self.stdout.write(
                self.style.SUCCESS("No duplicate usernames found.")
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {dupes.count()} username(s) with duplicates:\n"
            )
        )

        total_to_delete = self._display_duplicates(
            dupes, verbose=options["verbose"]
        )

        self.stdout.write(
            f"Summary: {total_to_delete} duplicate(s) to remove "
            f"across {dupes.count()} username(s).\n"
        )

        if options["delete"]:
            self._perform_deletion(dupes)
        else:
            self.stdout.write(
                "Run with --delete to remove duplicates."
            )

    def _display_duplicates(self, dupes, *, verbose):
        """Print each duplicate group. Returns total count to delete."""
        total = 0
        for entry in dupes:
            username = entry["username"]
            profiles = _rank_profiles(
                Profile.objects.filter(username=username)
            )
            keep, to_delete = profiles[0], profiles[1:]
            total += len(to_delete)

            self._print_group(username, entry["count"], keep, to_delete,
                              verbose=verbose)
        return total

    def _print_group(self, username, count, keep, to_delete, *,
                     verbose):
        """Print one duplicate group."""
        n = len(FIELDS_TO_CHECK)
        self.stdout.write(
            f"  Username: {self.style.SUCCESS(username)} "
            f"({count} records)"
        )
        self.stdout.write(
            f"    KEEP   id={keep.id} "
            f"({_completeness(keep)}/{n} fields)"
        )
        if verbose:
            self._print_fields(keep)

        for p in to_delete:
            self.stdout.write(
                self.style.ERROR(
                    f"    DELETE id={p.id} "
                    f"({_completeness(p)}/{n} fields)"
                )
            )
            if verbose:
                self._print_fields(p)

        self.stdout.write("")

    def _print_fields(self, profile):
        """Print non-empty field values for a profile."""
        for field in FIELDS_TO_CHECK:
            val = getattr(profile, field, "")
            if val:
                self.stdout.write(f"             {field}: {val}")

    def _perform_deletion(self, dupes):
        """Delete duplicate profiles after confirmation."""
        confirm = input("Type 'yes' to proceed with deletion: ")
        if confirm != "yes":
            self.stdout.write(self.style.WARNING("Aborted."))
            return

        deleted = 0
        for entry in dupes:
            profiles = _rank_profiles(
                Profile.objects.filter(username=entry["username"])
            )
            for p in profiles[1:]:
                p.delete()
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} duplicate profile(s)."
            )
        )
