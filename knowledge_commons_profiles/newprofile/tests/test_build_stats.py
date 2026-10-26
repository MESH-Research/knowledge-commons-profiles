"""
Tests for the build_stats management command
"""

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import UserStats

BUILD_STATS = (
    "knowledge_commons_profiles.newprofile.management.commands.build_stats"
)


def _record(name="University of Testlandia", lat=51.5, lon=-0.1):
    return SimpleNamespace(
        id=1,
        ror_id="https://ror.org/abc123",
        institution_name=name,
        country="Testlandia",
        lat=lat,
        lon=lon,
    )


def _user(user_id, record=None, registered_year=2020, weeks_ago=10):
    now = datetime.datetime.now(tz=datetime.UTC)
    return {
        "id": user_id,
        "display_name": f"User {user_id}",
        "user_login": f"user{user_id}",
        "user_email": f"user{user_id}@example.org",
        "institution": record.institution_name if record else None,
        "latest_activity": now - datetime.timedelta(weeks=weeks_ago),
        "user_registered": datetime.datetime(
            registered_year, 6, 1, tzinfo=datetime.UTC
        ),
        "profile": f"https://hcommons.org/members/user{user_id}",
        "ror": None,
        "ror_record": record,
        "canonical_institution_name": (
            record.institution_name if record else None
        ),
        "country": record.country if record else None,
    }


def _users_generator(users):
    """
    Mimic a streaming source: the command must not need a list
    """
    yield from users


class BuildStatsCommandTests(TestCase):
    def _run(self, users):
        with patch(f"{BUILD_STATS}.WpUser") as wp_user:
            wp_user.iter_user_data.return_value = _users_generator(users)
            wp_user.get_user_data.side_effect = AssertionError(
                "build_stats should stream users, not load them all"
            )
            call_command("build_stats")

    def test_creates_single_stats_row_from_streamed_users(self):
        record = _record()
        users = [_user(1, record), _user(2, record), _user(3)]

        self._run(users)

        self.assertEqual(UserStats.objects.count(), 1)
        stats = UserStats.objects.get()
        self.assertEqual(stats.user_count, 3)

    def test_counts_active_users_in_each_window(self):
        users = [
            _user(1, weeks_ago=10),
            _user(2, weeks_ago=80),
            _user(3, weeks_ago=150),
            _user(4, weeks_ago=400),
        ]

        self._run(users)

        stats = UserStats.objects.get()
        self.assertEqual(stats.user_count_active, 3)
        self.assertEqual(str(stats.user_count_active_two), "2")
        self.assertEqual(str(stats.user_count_active_three), "1")

    def test_map_points_aggregate_by_institution(self):
        record = _record()
        users = [_user(1, record), _user(2, record)]

        self._run(users)

        stats = UserStats.objects.get()
        latlong = json.loads(stats.latlong)
        self.assertEqual(
            latlong["University of Testlandia"], [51.5, -0.1, 2]
        )

    def test_signups_by_year_are_recorded(self):
        users = [
            _user(1, registered_year=2020),
            _user(2, registered_year=2020),
            _user(3, registered_year=2021),
        ]

        self._run(users)

        stats = UserStats.objects.get()
        years = json.loads(stats.years.replace("'", '"'))
        data = json.loads(stats.data)
        by_year = dict(zip(years, data, strict=True))
        self.assertEqual(by_year["2020"], 2)
        self.assertEqual(by_year["2021"], 1)

    def test_rerun_replaces_rather_than_accumulates(self):
        self._run([_user(1), _user(2)])
        self._run([_user(1)])

        self.assertEqual(UserStats.objects.count(), 1)
        self.assertEqual(UserStats.objects.get().user_count, 1)

    def test_old_row_survives_if_rebuild_fails(self):
        self._run([_user(1), _user(2)])
        self.assertEqual(UserStats.objects.get().user_count, 2)

        with (
            patch(f"{BUILD_STATS}.WpUser") as wp_user,
            patch(
                f"{BUILD_STATS}.UserStats.objects.create",
                side_effect=RuntimeError("boom"),
            ),
        ):
            wp_user.iter_user_data.return_value = _users_generator(
                [_user(1)]
            )
            with self.assertRaises(RuntimeError):
                call_command("build_stats")

        self.assertEqual(UserStats.objects.count(), 1)
        self.assertEqual(UserStats.objects.get().user_count, 2)
