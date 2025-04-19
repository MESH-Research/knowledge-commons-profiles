"""
A management command that fetches and installs the latest ROR support
"""

import logging

from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import RORLookup
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    A management command that fetches and installs the latest ROR support
    """

    help = "Matches current WordPress users against ROR"

    def handle(self, *args, **options):
        logger.info("Installing ROR lookups.")

        users: list[dict[str, str | WpUser]] = WpUser.get_user_data(limit=50)

        for user in track(users):
            RORLookup.lookup(text=user["institution"])

        logger.info("ROR lookups installed.")
