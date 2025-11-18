"""
A management command to generate a CSV of all spammer users
"""

import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Extract data from a CSV of all users"

    def handle(self, *args, **options):

        fieldnames = [
            "id",
            "display_name",
            "user_login",
            "user_email",
            "date_registered",
        ]

        users = WpUser.objects.filter(spam__gt=0)

        with Path("users-spam.csv").open("w", newline="") as csvfile:
            csvwriter = csv.writer(
                csvfile,
                delimiter=" ",
                quotechar="|",
                quoting=csv.QUOTE_ALL,
            )
            # write the header row
            csvwriter.writerow(fieldnames)

            # write all rows
            for user_row in users:
                csvwriter.writerow(
                    [
                        user_row.id,
                        user_row.display_name,
                        user_row.user_login,
                        user_row.user_email,
                        user_row.user_registered,
                        user_row.user_status,
                    ]
                )
