"""
A management command to generate a CSV of all users
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Generate a CSV of all users"

    def handle(self, *args, **options):

        logger.info("Generating users.csv...")

        with Path("users.csv").open(
            "w",
            encoding="utf-8",
        ) as out_file:
            WpUser.get_user_data(out_file)

        logger.info("Generated users.csv")
