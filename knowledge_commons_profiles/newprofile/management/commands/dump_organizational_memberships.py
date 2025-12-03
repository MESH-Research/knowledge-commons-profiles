"""
A management command to dump users and their memberships
"""

import csv
import logging
import time
from pathlib import Path

import rich
from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Dump users and their memberships"

    def handle(self, *args, **options):
        # load a list of items already processed from /home/martin/done.txt
        done = set()
        if Path("/home/martin/done.txt").exists():
            with Path("/home/martin/done.txt").open("r") as f:
                for line in f:
                    done.add(line.strip())

        # get a list of all users
        profiles = Profile.objects.all()

        # for user in track(profiles):
        for user in track(profiles):

            if user.username in done:
                continue

            time.sleep(1)

            rich.print(f"Processing: {user.username}")

            ExternalSync.sync(user, cache=False, webhooks=False)

            # if /home/martin/user_memberships does not exist, write the
            # fieldname headers to a new file there

            fieldnames = [
                "user_login",
                "mla",
                "arlisna",
                "msu",
                "up",
                "hastac",
                "sah",
                "stemedplus",
            ]

            if not Path("/home/martin/user_memberships.csv").exists():
                with Path("/home/martin/user_memberships.csv").open(
                    "w", newline=""
                ) as csvfile:
                    csvwriter = csv.writer(
                        csvfile,
                        delimiter=",",
                        quotechar="'",
                        quoting=csv.QUOTE_ALL,
                    )
                    csvwriter.writerow(fieldnames)
                    csvfile.flush()

            # now append to that file
            with Path("/home/martin/user_memberships.csv").open(
                "a", newline=""
            ) as csvfile:
                csvwriter = csv.writer(
                    csvfile,
                    delimiter=",",
                    quotechar="'",
                    quoting=csv.QUOTE_ALL,
                )

                memberships = user.get_external_memberships()

                csvwriter.writerow(
                    [
                        user.username,
                        memberships.get("MLA", False),
                        memberships.get("ARLISNA", False),
                        memberships.get("MSU", False),
                        memberships.get("UP", False),
                        memberships.get("HASTAC", False),
                        memberships.get("SAH", False),
                        memberships.get("STEMEDPLUS", False),
                    ]
                )

                csvfile.flush()

                done.add(user.username)

                # write the done list to /home/martin/done.txt
                with Path("/home/martin/done.txt").open("a") as f:
                    f.write(f"{user.username}\n")
