"""
Store stats in the DB

"""

import contextlib
import datetime
import json
from collections import Counter
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge_commons_profiles.newprofile.models import UserStats
from knowledge_commons_profiles.newprofile.models import WpUser

if TYPE_CHECKING:
    from collections.abc import Iterable

MAP_LIMIT = 200
COUNTER_LIMIT = 20
FIRST_YEAR = 2005


class StatsAccumulator:
    """
    Accumulates dashboard statistics one user at a time so that the full
    user list never has to be held in memory
    """

    def __init__(self, now: datetime.datetime | None = None):
        self.now = now or datetime.datetime.now(tz=datetime.UTC)

        self.user_count = 0
        self.user_count_active = 0
        self.user_count_active_two = 0
        self.user_count_active_three = 0

        self.signups_by_year: dict[str, int] = {
            str(year): 0 for year in range(FIRST_YEAR, self.now.year + 1)
        }
        self.lat_long: dict[str, list] = {}
        self.institutions: Counter = Counter()
        self.emails: Counter = Counter()

    def add(self, user: dict) -> None:
        """
        Fold a single user dict into the running totals
        """
        self.user_count += 1

        if (
            user["ror_record"] is not None
            and user["canonical_institution_name"] is not None
        ):
            if user["canonical_institution_name"]:
                self.institutions[user["canonical_institution_name"]] += 1

            # count the email domain if found
            with contextlib.suppress(IndexError):
                if user["user_email"]:
                    domain = user["user_email"].split("@")[1]

                    if domain not in settings.EXCLUDE_STATS_EMAILS:
                        self.emails[domain] += 1

            current_score = self.lat_long.get(
                user["canonical_institution_name"], [0, 0, 0]
            )[2]

            self.lat_long[user["canonical_institution_name"]] = [
                user["ror_record"].lat,
                user["ror_record"].lon,
                current_score + 1,
            ]

        with contextlib.suppress(ValueError, TypeError, KeyError):
            if user["user_registered"] is not None:
                self.signups_by_year[str(user["user_registered"].year)] += 1

        if user["latest_activity"] is not None:
            if user["latest_activity"] > self.now - datetime.timedelta(
                weeks=166
            ):
                self.user_count_active += 1

            if user["latest_activity"] > self.now - datetime.timedelta(
                weeks=104
            ):
                self.user_count_active_two += 1

            if user["latest_activity"] > self.now - datetime.timedelta(
                weeks=52
            ):
                self.user_count_active_three += 1

    def add_all(self, users: Iterable[dict]) -> None:
        for user in users:
            self.add(user)

    def as_model_fields(self) -> dict:
        """
        Render the totals as the field values for a UserStats row
        """
        top_map = dict(
            sorted(
                self.lat_long.items(),
                key=lambda item: item[1][2],
                reverse=True,
            )[:MAP_LIMIT]
        )
        top_institutions = dict(self.institutions.most_common(COUNTER_LIMIT))
        top_emails = dict(self.emails.most_common(COUNTER_LIMIT))

        return {
            "user_count": self.user_count,
            "user_count_active": self.user_count_active,
            "user_count_active_two": self.user_count_active_two,
            "user_count_active_three": self.user_count_active_three,
            "years": str(list(self.signups_by_year.keys())),
            "data": str(list(self.signups_by_year.values())),
            "latlong": json.dumps(top_map),
            "topinsts": str(list(top_institutions.keys())),
            "topinstscount": str(list(top_institutions.values())),
            "emails": str(list(top_emails.keys())),
            "emailcount": str(list(top_emails.values())),
        }


class Command(BaseCommand):
    """
    Command to build stats
    """

    help = "Build stats"

    def add_arguments(self, parser):
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=1000,
            help="Number of users to fetch from WordPress per query",
        )

    def handle(self, *args, **options):
        accumulator = StatsAccumulator()
        accumulator.add_all(
            WpUser.iter_user_data(chunk_size=options["chunk_size"])
        )

        fields = accumulator.as_model_fields()

        # Replace the row atomically so that a concurrent dashboard request
        # sees either the previous stats or the new ones, never nothing.
        with transaction.atomic():
            UserStats.objects.all().delete()
            UserStats.objects.create(**fields)
