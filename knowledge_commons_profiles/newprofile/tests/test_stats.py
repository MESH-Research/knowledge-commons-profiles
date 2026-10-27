"""
Tests for the user stats dashboard, CSV export and map configuration
"""

import base64
import csv
import datetime
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.newprofile import stats_utils

STATS_UTILS = "knowledge_commons_profiles.newprofile.stats_utils"
STATS_VIEWS = "knowledge_commons_profiles.newprofile.views.stats"

TILE_URL = "https://tiles.example.org/{z}/{x}/{y}.png"
TILE_ATTRIBUTION = "Map data from Example Tiles"


STATS_CREDENTIALS = ("stats", "pw")


def _basic_auth_header() -> dict[str, str]:
    """
    Build request headers that authenticate as the stats user
    """
    token = base64.b64encode(":".join(STATS_CREDENTIALS).encode()).decode()
    return {"authorization": f"Basic {token}"}


def _ror_record(
    ror_id: str = "https://ror.org/abc123",
    name: str = "University of Testlandia",
    country: str = "Testlandia",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        ror_id=ror_id,
        institution_name=name,
        country=country,
        lat=51.5,
        lon=-0.1,
    )


def _user_row(
    user_id: int = 1,
    institution: str | None = "Univ of Testlandia",
) -> dict:
    return {
        "id": user_id,
        "display_name": f"User {user_id}",
        "user_login": f"user{user_id}",
        "user_email": f"user{user_id}@example.org",
        "institution": institution,
        "latest_activity": datetime.datetime(
            2026, 1, 1, tzinfo=datetime.UTC
        ),
        "user_registered": datetime.datetime(
            2020, 1, 1, tzinfo=datetime.UTC
        ),
    }


def _patch_user_data_sources(users, lookups, records):
    """
    Patch the ORM boundaries that get_user_data reads from.

    :param users: list of user dicts returned by the WpUser queryset
    :param lookups: list of RORLookup-like objects (text, ror)
    :param records: dict of RORRecord-like objects keyed by id
    """
    wp_user = MagicMock()
    wp_user.objects = FakeUserQuerySet(users)

    ror_lookup = MagicMock()
    ror_lookup.objects.filter.return_value = lookups

    ror_record = MagicMock()
    ror_record.objects.in_bulk.return_value = records

    return (
        patch(f"{STATS_UTILS}.WpUser", wp_user),
        patch(f"{STATS_UTILS}.RORLookup", ror_lookup),
        patch(f"{STATS_UTILS}.RORRecord", ror_record),
    )


class GetUserDataCountryTests(SimpleTestCase):
    """
    get_user_data should expose the country of the matched ROR institution
    """

    def _run(self, users, lookups, records):
        patches = _patch_user_data_sources(users, lookups, records)
        buffer = io.StringIO()

        with patches[0], patches[1], patches[2]:
            result = stats_utils.get_user_data(output_stream=buffer)

        buffer.seek(0)
        return result, list(csv.DictReader(buffer))

    def test_csv_has_country_for_ror_matched_user(self):
        record = _ror_record(country="Testlandia")
        lookup = SimpleNamespace(text="Univ of Testlandia", ror=record)

        _, rows = self._run([_user_row()], [lookup], {record.id: record})

        self.assertEqual(rows[0]["country"], "Testlandia")

    def test_csv_country_is_empty_when_no_ror_match(self):
        _, rows = self._run([_user_row(institution="Unknown Place")], [], {})

        self.assertEqual(rows[0]["country"], "")

    def test_csv_country_is_empty_when_user_has_no_institution(self):
        _, rows = self._run([_user_row(institution=None)], [], {})

        self.assertEqual(rows[0]["country"], "")

    def test_user_dicts_carry_country(self):
        record = _ror_record(country="Testlandia")
        lookup = SimpleNamespace(text="Univ of Testlandia", ror=record)

        users, _ = self._run([_user_row()], [lookup], {record.id: record})

        self.assertEqual(users[0]["country"], "Testlandia")

    def test_user_dicts_country_is_none_without_match(self):
        users, _ = self._run([_user_row(institution="Nowhere")], [], {})

        self.assertIsNone(users[0]["country"])

    def test_csv_still_has_existing_columns(self):
        record = _ror_record()
        lookup = SimpleNamespace(text="Univ of Testlandia", ror=record)

        _, rows = self._run([_user_row()], [lookup], {record.id: record})

        self.assertEqual(rows[0]["ror_institution"], record.institution_name)
        self.assertEqual(rows[0]["ror_id"], record.ror_id)
        self.assertEqual(
            rows[0]["profile"], "https://hcommons.org/members/user1"
        )


class MapTileSettingsTests(SimpleTestCase):
    """
    The tile server configuration must not be hardcoded in the template
    """

    def test_default_tile_url_is_https_template(self):
        url = settings.STATS_MAP_TILE_URL

        self.assertTrue(url.startswith("https://"))
        for placeholder in ("{z}", "{x}", "{y}"):
            self.assertIn(placeholder, url)

    def test_default_attribution_is_set(self):
        self.assertTrue(settings.STATS_MAP_TILE_ATTRIBUTION)

    def test_default_max_zoom_is_positive_integer(self):
        self.assertIsInstance(settings.STATS_MAP_TILE_MAX_ZOOM, int)
        self.assertGreater(settings.STATS_MAP_TILE_MAX_ZOOM, 0)


def _user_stats(latlong: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        user_count=10,
        user_count_active=5,
        user_count_active_two="4",
        user_count_active_three="3",
        years="['2020', '2021']",
        data="[1, 2]",
        latlong=json.dumps(
            latlong
            if latlong is not None
            else {"University of Testlandia": [51.5, -0.1, 3]}
        ),
        topinsts="['University of Testlandia']",
        topinstscount="[3]",
        emails="['example.org']",
        emailcount="[3]",
        country_count=173,
        countries=json.dumps({"GR": 2, "US": 1}),
    )


@override_settings(
    BASICAUTH_USERS=dict([STATS_CREDENTIALS]),
    STATS_MAP_TILE_URL=TILE_URL,
    STATS_MAP_TILE_ATTRIBUTION=TILE_ATTRIBUTION,
    STATS_MAP_TILE_MAX_ZOOM=7,
)
class StatsBoardMapTests(SimpleTestCase):
    """
    The stats dashboard should render the map from configuration
    """

    def _get(self, latlong=None):
        user_stats = MagicMock()
        user_stats.objects.all.return_value.first.return_value = _user_stats(
            latlong
        )
        wp_user = MagicMock()
        wp_user.get_user_data.return_value = []

        with (
            patch(f"{STATS_VIEWS}.UserStats", user_stats),
            patch(f"{STATS_VIEWS}.WpUser", wp_user),
        ):
            return self.client.get(
                reverse("stats"), headers=_basic_auth_header()
            )

    def test_requires_basic_auth(self):
        response = self.client.get(reverse("stats"))

        self.assertEqual(response.status_code, 401)

    def test_configured_tile_url_is_in_context(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["map_tile_url"], TILE_URL)

    def test_configured_attribution_is_in_context(self):
        response = self._get()

        self.assertEqual(
            response.context["map_tile_attribution"], TILE_ATTRIBUTION
        )

    def test_configured_max_zoom_is_in_context(self):
        response = self._get()

        self.assertEqual(response.context["map_tile_max_zoom"], 7)

    def test_page_uses_configured_tile_url_not_hardcoded_one(self):
        response = self._get()
        content = response.content.decode()

        self.assertIn(TILE_URL, content)
        self.assertNotIn("tile.openstreetmap.org", content)

    def test_page_embeds_map_points_as_json(self):
        response = self._get(
            latlong={"University of Testlandia": [51.5, -0.1, 3]}
        )
        content = response.content.decode()

        self.assertIn("University of Testlandia", content)
        self.assertIn("51.5", content)
        self.assertIn("-0.1", content)

    def test_page_has_hidden_map_unavailable_fallback(self):
        response = self._get()

        self.assertContains(
            response, 'id="map_stats_unavailable"', count=1
        )
        self.assertRegex(
            response.content.decode(),
            r'<p id="map_stats_unavailable"[^>]*\bhidden\b',
        )

    def test_country_count_is_in_context_and_shown(self):
        response = self._get()

        self.assertEqual(response.context["country_count"], 173)
        self.assertContains(response, "173")

    def test_members_per_country_is_in_context_and_embedded(self):
        response = self._get()

        self.assertEqual(
            response.context["countries"], {"GR": 2, "US": 1}
        )
        self.assertContains(response, 'id="country_stats_data"', count=1)
        self.assertContains(response, '"GR": 2')

    def test_page_sends_referrer_with_tile_requests(self):
        """
        The OSM tile policy forbids a Referrer-Policy that hides the
        referer. The page must opt tile requests back in.
        """
        response = self._get()
        content = response.content.decode()

        self.assertIn("strict-origin-when-cross-origin", content)


@override_settings(BASICAUTH_USERS=dict([STATS_CREDENTIALS]))
class StatsTableCountryTests(SimpleTestCase):
    """
    The on-page user table should show the matched institution's country
    """

    def test_table_shows_country(self):
        record = _ror_record(country="Narnia")
        user = _user_row()
        user["profile"] = "https://hcommons.org/members/user1"
        user["ror_record"] = record
        user["country"] = record.country

        wp_user = MagicMock()
        wp_user.get_user_data.return_value = [user]

        with patch(f"{STATS_VIEWS}.WpUser", wp_user):
            response = self.client.get(
                reverse("stats_table"),
                headers=_basic_auth_header(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Narnia", response.content.decode())


@override_settings(BASICAUTH_USERS=dict([STATS_CREDENTIALS]))
class StatsDownloadCountryTests(SimpleTestCase):
    """
    The downloadable CSV should include the country column end to end
    """

    def test_download_includes_country_column(self):
        record = _ror_record(country="Testlandia")
        lookup = SimpleNamespace(text="Univ of Testlandia", ror=record)
        patches = _patch_user_data_sources(
            [_user_row()], [lookup], {record.id: record}
        )

        with patches[0], patches[1], patches[2]:
            response = self.client.get(
                reverse("get_stats_csv"),
                headers=_basic_auth_header(),
            )

        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0]["country"], "Testlandia")
        self.assertEqual(rows[0]["ror_institution"], record.institution_name)


class FakeUserQuerySet:
    """
    An in-memory stand-in for the WpUser queryset, supporting the subset of
    queryset operations needed to page through users by primary key.
    """

    def __init__(self, rows):
        self.rows = list(rows)

    def annotate(self, **kwargs):
        return FakeUserQuerySet(self.rows)

    def values(self, *fields):
        return FakeUserQuerySet(self.rows)

    def order_by(self, *fields):
        return FakeUserQuerySet(sorted(self.rows, key=lambda r: r["id"]))

    def filter(self, **kwargs):
        rows = self.rows
        if "pk__gt" in kwargs:
            rows = [r for r in rows if r["id"] > kwargs["pk__gt"]]
        if "id__gt" in kwargs:
            rows = [r for r in rows if r["id"] > kwargs["id__gt"]]
        return FakeUserQuerySet(rows)

    def iterator(self, chunk_size=None):
        return iter(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, item):
        result = self.rows[item]
        if isinstance(item, slice):
            return FakeUserQuerySet(result)
        return result


class IterUserDataTests(SimpleTestCase):
    """
    iter_user_data should stream users in bounded chunks
    """

    def _run(self, users, lookups, records, **kwargs):
        wp_user = MagicMock()
        wp_user.objects = FakeUserQuerySet(users)

        ror_lookup = MagicMock()
        lookup_calls = []

        def _filter(**filter_kwargs):
            texts = set(filter_kwargs.get("text__in", []))
            lookup_calls.append(texts)
            return [lk for lk in lookups if lk.text in texts]

        ror_lookup.objects.filter.side_effect = _filter

        ror_record = MagicMock()
        ror_record.objects.in_bulk.side_effect = lambda ids: {
            k: v for k, v in records.items() if k in set(ids)
        }

        with (
            patch(f"{STATS_UTILS}.WpUser", wp_user),
            patch(f"{STATS_UTILS}.RORLookup", ror_lookup),
            patch(f"{STATS_UTILS}.RORRecord", ror_record),
        ):
            result = list(stats_utils.iter_user_data(**kwargs))

        return result, lookup_calls

    def test_yields_every_user_once_across_chunks(self):
        users = [
            _user_row(user_id=i, institution=f"Inst {i}") for i in range(1, 8)
        ]

        result, _ = self._run(users, [], {}, chunk_size=3)

        self.assertEqual([u["id"] for u in result], [1, 2, 3, 4, 5, 6, 7])

    def test_yields_users_in_id_order_even_if_source_is_unordered(self):
        users = [_user_row(user_id=i) for i in (5, 2, 9, 1)]

        result, _ = self._run(users, [], {}, chunk_size=2)

        self.assertEqual([u["id"] for u in result], [1, 2, 5, 9])

    def test_respects_limit(self):
        users = [_user_row(user_id=i) for i in range(1, 11)]

        result, _ = self._run(users, [], {}, limit=4, chunk_size=3)

        self.assertEqual([u["id"] for u in result], [1, 2, 3, 4])

    def test_enriches_each_user_with_ror_data(self):
        record = _ror_record(country="Testlandia")
        lookup = SimpleNamespace(text="Univ of Testlandia", ror=record)
        users = [
            _user_row(user_id=1),
            _user_row(user_id=2, institution="Nowhere"),
        ]

        result, _ = self._run(
            users, [lookup], {record.id: record}, chunk_size=1
        )

        self.assertEqual(result[0]["country"], "Testlandia")
        self.assertEqual(
            result[0]["canonical_institution_name"], record.institution_name
        )
        self.assertEqual(
            result[0]["profile"], "https://hcommons.org/members/user1"
        )
        self.assertIsNone(result[1]["ror_record"])
        self.assertIsNone(result[1]["country"])
        self.assertEqual(result[1]["canonical_institution_name"], "Nowhere")

    def test_ror_lookups_are_bounded_by_chunk_size(self):
        chunk_size = 4
        users = [
            _user_row(user_id=i, institution=f"Inst {i}") for i in range(1, 11)
        ]

        _, lookup_calls = self._run(users, [], {}, chunk_size=chunk_size)

        self.assertTrue(lookup_calls)
        self.assertTrue(
            all(len(texts) <= chunk_size for texts in lookup_calls)
        )
        self.assertEqual(
            set().union(*lookup_calls), {f"Inst {i}" for i in range(1, 11)}
        )

    def test_is_lazy(self):
        users = [_user_row(user_id=i) for i in range(1, 4)]
        wp_user = MagicMock()
        wp_user.objects = FakeUserQuerySet(users)

        with patch(f"{STATS_UTILS}.WpUser", wp_user):
            iterator = stats_utils.iter_user_data(chunk_size=1)
            self.assertFalse(isinstance(iterator, list))

    def test_empty_source_yields_nothing(self):
        result, _ = self._run([], [], {}, chunk_size=5)

        self.assertEqual(result, [])


@override_settings(BASICAUTH_USERS=dict([STATS_CREDENTIALS]))
class StatsBoardWithoutStatsTests(SimpleTestCase):
    """
    The dashboard should not crash when the stats row has not been built
    """

    def test_returns_service_unavailable_when_no_stats_row(self):
        user_stats = MagicMock()
        user_stats.objects.all.return_value.first.return_value = None
        wp_user = MagicMock()
        wp_user.get_user_data.return_value = []

        with (
            patch(f"{STATS_VIEWS}.UserStats", user_stats),
            patch(f"{STATS_VIEWS}.WpUser", wp_user),
        ):
            response = self.client.get(
                reverse("stats"), headers=_basic_auth_header()
            )

        self.assertEqual(response.status_code, 503)


@override_settings(BASICAUTH_USERS=dict([STATS_CREDENTIALS]))
class StatsBoardCountryGroupTests(SimpleTestCase):
    """
    The dashboard offers a per-group country breakdown chosen from a dropdown
    """

    def _get(self):
        user_stats = MagicMock()
        user_stats.objects.all.return_value.first.return_value = (
            _user_stats()
        )
        wp_user = MagicMock()
        wp_user.get_user_data.return_value = []

        with (
            patch(f"{STATS_VIEWS}.UserStats", user_stats),
            patch(f"{STATS_VIEWS}.WpUser", wp_user),
        ):
            return self.client.get(
                reverse("stats"), headers=_basic_auth_header()
            )

    def test_country_groups_are_in_context_alphabetically(self):
        response = self._get()

        names = [g["name"] for g in response.context["country_groups"]]
        self.assertGreater(len(names), 1)
        self.assertEqual(names, sorted(names, key=str.casefold))

    def test_country_groups_reflect_stored_counts(self):
        response = self._get()

        anglophone = next(
            g
            for g in response.context["country_groups"]
            if g["name"] == "Anglophone"
        )
        self.assertEqual(
            anglophone["countries"],
            [
                {
                    "code": "US",
                    "name": "United States",
                    "count": 1,
                    "cumulative": 1,
                }
            ],
        )

    def test_page_table_has_a_cumulative_column(self):
        response = self._get()
        content = response.content.decode()

        self.assertIn("Cumulative", content)

    def test_page_embeds_country_groups_as_json(self):
        response = self._get()
        content = response.content.decode()

        self.assertIn('id="country_group_data"', content)
        self.assertIn("Anglophone", content)

    def test_page_has_group_dropdown_with_alphabetical_options(self):
        response = self._get()
        content = response.content.decode()

        self.assertIn('id="country_group_select"', content)
        self.assertLess(content.index(">Africa<"), content.index(">Europe<"))
        self.assertLess(
            content.index(">Europe<"), content.index(">Global South<")
        )
