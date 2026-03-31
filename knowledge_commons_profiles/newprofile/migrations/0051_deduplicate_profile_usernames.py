"""
Data migration to deduplicate Profile records with the same username.

For each group of duplicates, keeps the most complete record (most non-empty
fields) and deletes the rest. This must run before adding the unique
constraint on Profile.username.
"""

import logging

from django.db import migrations
from django.db.models import Count

logger = logging.getLogger(__name__)

FIELDS_TO_CHECK = [
    "name",
    "title",
    "affiliation",
    "email",
    "orcid",
    "twitter",
    "github",
    "mastodon",
    "about",
    "education",
    "publications",
    "projects",
    "memberships",
]


def count_non_empty_fields(profile):
    """Count how many of the key fields have non-empty values."""
    count = 0
    for field in FIELDS_TO_CHECK:
        val = getattr(profile, field, None)
        if val:
            count += 1
    return count


def deduplicate_profiles(apps, schema_editor):
    Profile = apps.get_model("newprofile", "Profile")

    dupes = (
        Profile.objects.values("username")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    if not dupes.exists():
        logger.info("No duplicate usernames found -- nothing to do.")
        return

    total_deleted = 0

    for entry in dupes:
        username = entry["username"]
        profiles = list(Profile.objects.filter(username=username).order_by("id"))

        # Sort by completeness (most non-empty fields first), then by id
        # (oldest first as tiebreaker)
        profiles.sort(key=lambda p: (-count_non_empty_fields(p), p.id))

        keep = profiles[0]
        to_delete = profiles[1:]

        for p in to_delete:
            logger.info(
                "Deleting duplicate Profile id=%s for username='%s' "
                "(keeping id=%s)",
                p.id,
                username,
                keep.id,
            )
            p.delete()
            total_deleted += 1

    logger.info(
        "Deduplication complete: removed %s duplicate profile(s).",
        total_deleted,
    )


def noop(apps, schema_editor):
    """Reverse migration is a no-op -- deleted data cannot be restored."""


class Migration(migrations.Migration):

    dependencies = [
        ("newprofile", "0050_add_show_works_chart"),
    ]

    operations = [
        migrations.RunPython(deduplicate_profiles, noop),
    ]
