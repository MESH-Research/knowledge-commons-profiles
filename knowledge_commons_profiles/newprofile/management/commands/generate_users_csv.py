"""
A management command to generate a CSV of all users
"""

import contextlib
import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connections
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import WpBpActivity
from knowledge_commons_profiles.newprofile.models import WpProfileFields
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Generate a CSV of all users"

    def query_count_all(self) -> int:
        return sum(len(c.queries) for c in connections.all())

    def handle(self, *args, **options):

        logger.info("Generating users.csv")

        users = (
            WpUser.objects.all()
            .prefetch_related("wpprofiledata_set__field")
            .prefetch_related("wpbpactivity_set")
        )

        logger.info("Got WordPress users (%s)", len(users))
        logger.info("This used %s queries", self.query_count_all())

        with Path("users.csv").open(
            "w",
            encoding="utf-8",
        ) as out_file:

            fieldnames = [
                "id",
                "display_name",
                "user_login",
                "user_email",
                "institution",
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

                activities = sorted(
                    wp_user.wpbpactivity_set.all(),
                    key=lambda a: a.date_recorded,
                    reverse=True,
                )

                # get profile data
                institution = ""
                for data in wp_user.wpprofiledata_set.all():
                    with contextlib.suppress(WpProfileFields.DoesNotExist):
                        if (
                            data.user_id == wp_user.id
                            and data.field.name
                            == "Institutional or Other Affiliation"
                        ):
                            institution = data.value
                            break
                try:
                    activity = next(
                        (activity for activity in activities),
                        None,
                    )

                    writer.writerow(
                        {
                            "id": wp_user.id,
                            "display_name": wp_user.display_name,
                            "user_login": wp_user.user_login,
                            "user_email": wp_user.user_email,
                            "institution": institution,
                            "date_registered": wp_user.user_registered,
                            "latest_activity": (
                                activity.date_recorded if activity else None
                            ),
                        }
                    )
                except WpBpActivity.DoesNotExist:
                    msg = f"User activity for {wp_user.user_login} not found"
                    logger.exception(msg=msg)

        logger.info("Total of: %s queries", self.query_count_all())
