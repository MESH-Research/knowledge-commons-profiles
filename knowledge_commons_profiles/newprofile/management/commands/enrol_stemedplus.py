"""
Bulk-enrol users on STEMEd+ from a file of email addresses.

Thin wrapper over ``society_enrolment.enrol_from_file``.
"""

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.society_enrolment import SocietySpec
from knowledge_commons_profiles.newprofile.society_enrolment import (
    enrol_from_file,
)

SPEC = SocietySpec(name="STEMED+")


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
        enrol_from_file(
            SPEC,
            options["file"],
            self.stdout,
            self.style,
            dry_run=options["dry_run"],
        )
