"""
A management command that matches users' institutions against ROR
"""

import logging

import requests
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import RORLookup
from knowledge_commons_profiles.newprofile.models import RORRecord
from knowledge_commons_profiles.newprofile.models import WpProfileData

logger = logging.getLogger(__name__)

INSTITUTION_FIELD = "Institutional or Other Affiliation"


def distinct_institutions() -> list[str]:
    """
    The distinct, non-empty institution strings users have entered
    """
    values = (
        WpProfileData.objects.filter(field__name=INSTITUTION_FIELD)
        .exclude(value__isnull=True)
        .exclude(value="")
        .order_by("value")
        .values_list("value", flat=True)
        .distinct()
    )

    seen: set[str] = set()
    institutions: list[str] = []

    for value in values.iterator(chunk_size=2000):
        text = value.strip() if value else ""

        if text and text not in seen:
            seen.add(text)
            institutions.append(text)

    return institutions


class Command(BaseCommand):
    """
    Build RORLookup rows for every distinct institution string users have
    entered, consulting the ROR API for strings not yet seen
    """

    help = "Matches current WordPress users' institutions against ROR"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete all existing ROR lookups before matching",
        )

    def handle(self, *args, **options):
        if not RORRecord.objects.exists():
            msg = "No ROR records are installed; run install_ror first."
            raise CommandError(msg)

        if options["delete"]:
            deleted, _ = RORLookup.objects.all().delete()
            self.stdout.write(f"Deleted {deleted} existing ROR lookups.")

        institutions = distinct_institutions()
        existing = set(RORLookup.objects.values_list("text", flat=True))

        self.stdout.write(
            f"{len(institutions)} distinct institutions, "
            f"{len(existing)} already looked up."
        )

        matched = 0
        unmatched = 0
        failed = 0
        skipped = 0

        for text in track(institutions, description="Matching ROR"):
            if text in existing:
                skipped += 1
                continue

            try:
                lookup = RORLookup.lookup(text=text)
            except (requests.RequestException, ValueError) as exc:
                failed += 1
                logger.warning("ROR lookup failed for %s: %s", text, exc)
                continue

            if lookup is not None and lookup.ror is not None:
                matched += 1
            else:
                unmatched += 1

        self.stdout.write(
            f"ROR matching complete: {matched} matched, "
            f"{unmatched} unmatched, {failed} failed, "
            f"{skipped} skipped (already looked up)."
        )
