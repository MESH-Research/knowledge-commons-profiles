"""
Store stats in the DB

"""

import contextlib
import datetime
import json
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import UserStats
from knowledge_commons_profiles.newprofile.models import WpUser

MAP_LIMIT = 200
COUNTER_LIMIT = 20


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Extract data from a CSV of all users"

    def process_users(  # noqa: PLR0913, C901
        self,
        emails,
        institutions,
        lat_long,
        signups_by_year,
        user_count_active,
        user_count_active_three,
        user_count_active_two,
        users,
    ):
        for user in users:
            if (
                user["ror_record"] is not None
                and user["canonical_institution_name"] is not None
            ):
                if (
                    user["canonical_institution_name"]
                    and user["canonical_institution_name"] != ""
                ):
                    institutions.append(user["canonical_institution_name"])

                # append the email domain if found
                with contextlib.suppress(IndexError):
                  
                    if user["user_email"]:
                        domain = user["user_email"].split("@")[1]

                        if domain not in settings.EXCLUDE_STATS_EMAILS:
                            emails.append(domain)


                current_score = lat_long.get(
                    user["canonical_institution_name"], [0, 0, 0]
                )[2]

                lat_long[user["canonical_institution_name"]] = [
                    user["ror_record"].lat,
                    user["ror_record"].lon,
                    current_score + 1,
                ]

            with contextlib.suppress(ValueError, TypeError):
                if user["user_registered"] is not None:
                    signups_by_year[str(user["user_registered"].year)] += 1

            if user["latest_activity"] is not None:
                if user["latest_activity"] > datetime.datetime.now(
                    tz=datetime.UTC
                ) - datetime.timedelta(weeks=166):
                    user_count_active += 1

                if user["latest_activity"] > datetime.datetime.now(
                    tz=datetime.UTC
                ) - datetime.timedelta(weeks=104):
                    user_count_active_two += 1

                if user["latest_activity"] > datetime.datetime.now(
                    tz=datetime.UTC
                ) - datetime.timedelta(weeks=52):
                    user_count_active_three += 1
        return (
            user_count_active,
            user_count_active_three,
            user_count_active_two,
        )

    def handle(self, *args, **options):
        users = WpUser.get_user_data()

        # build a dictionary of signups by year since 2014 and add
        # keys from 2014 to the current year with default value of zero
        signups_by_year = {}
        for year in range(
            2005, datetime.datetime.now(tz=datetime.UTC).year + 1
        ):
            signups_by_year[str(year)] = 0

        lat_long = {}
        institutions = []
        emails = []

        user_count_active = 0
        user_count_active_two = 0
        user_count_active_three = 0

        user_count_active, user_count_active_three, user_count_active_two = (
            self.process_users(
                emails,
                institutions,
                lat_long,
                signups_by_year,
                user_count_active,
                user_count_active_three,
                user_count_active_two,
                users,
            )
        )

        top200 = dict(
            sorted(
                lat_long.items(), key=lambda item: item[1][2], reverse=True
            )[:MAP_LIMIT]
        )

        institution_counter: Counter = Counter(institutions)
        institutions: dict[str:int] = dict(
            institution_counter.most_common(COUNTER_LIMIT)
        )

        email_counter: Counter = Counter(emails)
        emails: dict[str:int] = dict(email_counter.most_common(COUNTER_LIMIT))

        UserStats.objects.all().delete()

        UserStats.objects.create(
            user_count=len(users),
            user_count_active=user_count_active,
            user_count_active_two=user_count_active_two,
            user_count_active_three=user_count_active_three,
            years=str(list(signups_by_year.keys())),
            data=str(list(signups_by_year.values())),
            latlong=json.dumps(top200),
            topinsts=str(list(institutions.keys())),
            topinstscount=str(list(institutions.values())),
            emails=str(list(emails.keys())),
            emailcount=str(list(emails.values())),
        )
