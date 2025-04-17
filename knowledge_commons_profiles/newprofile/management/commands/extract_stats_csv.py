"""
A management command to generate a CSV of all users
"""

import contextlib
import csv
import datetime
import logging
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Extract data from a CSV of all users"

    def handle(self, *args, **options):

        with Path("users.csv").open(
            "r",
            encoding="utf-8",
        ) as in_file:

            fieldnames = [
                "id",
                "display_name",
                "user_login",
                "user_email",
                "date_registered",
                "latest_activity",
            ]

            reader = csv.DictReader(
                in_file,
                fieldnames=fieldnames,
                quotechar='"',
                quoting=csv.QUOTE_ALL,
                lineterminator="\n",
            )

            domain_counts = {}

            for user_row in reader:
                if user_row["latest_activity"] == "latest_activity":
                    continue

                try:
                    # parse "latest_activity" key as a python date
                    user_date_of_last_activity = datetime.datetime.strptime(
                        user_row["latest_activity"], "%Y-%m-%d %H:%M:%S+00:00"
                    ).replace(tzinfo=datetime.UTC)
                except (ValueError, TypeError):
                    continue

                if user_date_of_last_activity > datetime.datetime.now(
                    tz=datetime.UTC
                ) - timedelta(weeks=166):
                    with contextlib.suppress(IndexError):
                        domain = user_row["user_email"].split("@")[1]
                        domain_counts[domain] = (
                            domain_counts.get(domain, 0) + 1
                        )

            ordered_domains = {  # noqa: C416
                k: v
                for k, v in sorted(
                    domain_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            }

            table = Table(title="Most Used Institutions")

            table.add_column(
                "Domain", justify="right", style="cyan", no_wrap=True
            )
            table.add_column("Users", style="magenta")

            for _, (domain, count) in enumerate(ordered_domains.items()):
                table.add_row(domain, str(count))

            console = Console()
            console.print(table)

            return
