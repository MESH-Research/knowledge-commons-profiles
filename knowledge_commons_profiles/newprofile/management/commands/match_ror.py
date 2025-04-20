"""
A management command that fetches and installs the latest ROR support
"""

import logging
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import RORLookup
from knowledge_commons_profiles.newprofile.models import WpUser

if TYPE_CHECKING:
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    A management command that fetches and installs the latest ROR support
    """

    help = "Matches current WordPress users against ROR"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Whether to delete",
        )

    def handle(self, *args, **options):
        logger.info("Installing ROR lookups.")

        if options["delete"]:
            RORLookup.objects.all().delete()

        users: QuerySet[WpUser] | None = WpUser.get_user_data()

        for user in track(users):
            RORLookup.lookup(text=user.institution)
            return

        logger.info("ROR lookups installed.")
