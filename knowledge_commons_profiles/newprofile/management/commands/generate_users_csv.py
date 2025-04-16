"""
A management command to generate a CSV of all users
"""

import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import WpBpActivity
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Generate a CSV of all users"

    def handle(self, *args, **options):

        logger.info("Generating users.csv")
        users = WpUser.objects.all()

        logger.info("Got WordPress users (%s)", len(users))

        activities = WpBpActivity.objects.all().order_by("-date_recorded")

        logger.info("Got Activities (%s)", len(activities))

        with Path("users.csv").open(
            "w",
            encoding="utf-8",
        ) as out_file:

            fieldnames = [
                "id",
                "display_name",
                "user_login",
                "user_email",
                "date_registered",
                "latest_activity",
            ]

            writer = csv.DictWriter(
                out_file,
                fieldnames=fieldnames,
                quotechar='"',
                quoting=csv.QUOTE_ALL,
                lineterminator="\n",
            )
            writer.writeheader()

            for wp_user in track(users):

                try:
                    activity = next(
                        (
                            activity
                            for activity in activities
                            if activity.user_id == wp_user.id
                        ),
                        None,
                    )

                    writer.writerow(
                        {
                            "id": wp_user.id,
                            "display_name": wp_user.display_name,
                            "user_login": wp_user.user_login,
                            "user_email": wp_user.user_email,
                            "date_registered": wp_user.user_registered,
                            "latest_activity": (
                                activity.date_recorded if activity else None
                            ),
                        }
                    )
                except WpBpActivity.DoesNotExist:
                    msg = f"User activity for {wp_user.user_login} not found"
                    logger.exception(msg=msg)

            return
