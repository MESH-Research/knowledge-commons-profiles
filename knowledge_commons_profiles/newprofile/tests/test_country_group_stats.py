"""
Tests for country groups and the country_group_stats management command
"""

import io
from unittest.mock import patch

from django.core.management import CommandError
from django.core.management import call_command
from django.test import SimpleTestCase

from knowledge_commons_profiles.newprofile import country_groups
from knowledge_commons_profiles.newprofile.country_groups import COUNTRY_GROUPS
from knowledge_commons_profiles.newprofile.country_groups import COUNTRY_NAMES
from knowledge_commons_profiles.newprofile.country_groups import (
    UnknownGroupError,
)

COMMAND = (
    "knowledge_commons_profiles.newprofile.management.commands."
    "country_group_stats"
)


class CountryGroupDataTests(SimpleTestCase):
    """
    The static group definitions are internally consistent
    """

    def test_expected_groups_exist(self):
        for name in (
            "Global South",
            "Global North",
            "Anglophone",
            "Europe",
            "European Union",
            "Indo-China",
            "Latin America",
            "Sub-Saharan Africa",
            "Middle East and North Africa",
            "South Asia",
            "East Asia",
            "Oceania",
            "North America",
            "Caribbean",
            "Francophone",
            "Lusophone",
            "Hispanophone",
            "Commonwealth",
            "Nordic",
            "BRICS",
            "G7",
            "G20",
        ):
            self.assertIn(name, COUNTRY_GROUPS)

    def test_every_group_is_non_empty(self):
        for name, codes in COUNTRY_GROUPS.items():
            self.assertGreater(len(codes), 0, name)

    def test_every_group_code_has_a_country_name(self):
        for name, codes in COUNTRY_GROUPS.items():
            for code in codes:
                self.assertIn(code, COUNTRY_NAMES, f"{code} in {name}")

    def test_codes_are_upper_case_iso_alpha_2(self):
        for code in COUNTRY_NAMES:
            self.assertRegex(code, r"^[A-Z]{2}$")

    def test_sample_memberships(self):
        self.assertIn("GB", COUNTRY_GROUPS["Anglophone"])
        self.assertIn("US", COUNTRY_GROUPS["Anglophone"])
        self.assertIn("IN", COUNTRY_GROUPS["Global South"])
        self.assertIn("NG", COUNTRY_GROUPS["Global South"])
        self.assertNotIn("US", COUNTRY_GROUPS["Global South"])
        self.assertIn("US", COUNTRY_GROUPS["Global North"])
        self.assertIn("DE", COUNTRY_GROUPS["Europe"])
        self.assertIn("GB", COUNTRY_GROUPS["Europe"])
        self.assertNotIn("GB", COUNTRY_GROUPS["European Union"])
        self.assertIn("VN", COUNTRY_GROUPS["Indo-China"])
        self.assertIn("KH", COUNTRY_GROUPS["Indo-China"])
        self.assertIn("LA", COUNTRY_GROUPS["Indo-China"])
        self.assertIn("BR", COUNTRY_GROUPS["Latin America"])
        self.assertIn("MX", COUNTRY_GROUPS["Latin America"])

    def test_global_south_and_north_do_not_overlap(self):
        south = COUNTRY_GROUPS["Global South"]
        north = COUNTRY_GROUPS["Global North"]
        overlap = south & north
        self.assertEqual(overlap, frozenset())


class ResolveGroupTests(SimpleTestCase):
    """
    Group names resolve case-insensitively and through aliases
    """

    def test_exact_name(self):
        name, codes = country_groups.resolve_group("Global South")
        self.assertEqual(name, "Global South")
        self.assertEqual(codes, COUNTRY_GROUPS["Global South"])

    def test_case_and_whitespace_insensitive(self):
        name, _ = country_groups.resolve_group("  global SOUTH ")
        self.assertEqual(name, "Global South")

    def test_hyphen_and_space_variants(self):
        name, _ = country_groups.resolve_group("indochina")
        self.assertEqual(name, "Indo-China")
        name, _ = country_groups.resolve_group("Indo China")
        self.assertEqual(name, "Indo-China")

    def test_aliases(self):
        self.assertEqual(
            country_groups.resolve_group("EU")[0], "European Union"
        )
        self.assertEqual(
            country_groups.resolve_group("MENA")[0],
            "Middle East and North Africa",
        )
        self.assertEqual(
            country_groups.resolve_group("English-speaking")[0], "Anglophone"
        )

    def test_unknown_group_raises(self):
        with self.assertRaises(UnknownGroupError):
            country_groups.resolve_group("Atlantis")


class GroupMemberCountsTests(SimpleTestCase):
    """
    Counts are filtered to the group and ordered for display
    """

    def test_only_group_countries_are_returned(self):
        codes = frozenset({"VN", "KH", "LA"})
        counts = {"VN": 12, "KH": 3, "US": 500, "GB": 90}

        rows = country_groups.group_member_counts(codes, counts)

        self.assertEqual({code for code, _, _ in rows}, {"VN", "KH"})

    def test_rows_carry_country_names(self):
        codes = frozenset({"VN"})

        rows = country_groups.group_member_counts(codes, {"VN": 1})

        self.assertEqual(rows, [("VN", "Vietnam", 1)])

    def test_sorted_by_count_desc_then_name(self):
        codes = frozenset({"VN", "KH", "LA", "TH"})
        counts = {"VN": 3, "KH": 7, "LA": 3, "TH": 1}

        rows = country_groups.group_member_counts(codes, counts)

        self.assertEqual(
            [code for code, _, _ in rows], ["KH", "LA", "VN", "TH"]
        )

    def test_zero_counts_excluded_by_default(self):
        codes = frozenset({"VN", "KH"})

        rows = country_groups.group_member_counts(codes, {"VN": 2})

        self.assertEqual([code for code, _, _ in rows], ["VN"])

    def test_zero_counts_included_on_request(self):
        codes = frozenset({"VN", "KH"})

        rows = country_groups.group_member_counts(
            codes, {"VN": 2}, include_zero=True
        )

        self.assertEqual(rows[-1], ("KH", "Cambodia", 0))


class CountryGroupStatsCommandTests(SimpleTestCase):
    """
    The management command renders a table from the stored country counts
    """

    def _run(self, *args):
        out = io.StringIO()
        call_command("country_group_stats", *args, stdout=out)
        return out.getvalue()

    def test_prints_group_countries_with_counts_and_total(self):
        with patch(
            f"{COMMAND}.load_country_counts",
            return_value={"VN": 12, "KH": 3, "US": 500},
        ):
            output = self._run("Indo-China")

        self.assertIn("Vietnam", output)
        self.assertIn("12", output)
        self.assertIn("Cambodia", output)
        self.assertIn("3", output)
        self.assertNotIn("United States", output)
        self.assertIn("15", output)

    def test_group_name_may_be_given_as_separate_words(self):
        with patch(
            f"{COMMAND}.load_country_counts",
            return_value={"IN": 4},
        ):
            output = self._run("global", "south")

        self.assertIn("India", output)
        self.assertIn("Global South", output)

    def test_show_zero_lists_countries_without_members(self):
        with patch(
            f"{COMMAND}.load_country_counts", return_value={"VN": 12}
        ):
            output = self._run("Indo-China", "--show-zero")

        self.assertIn("Laos", output)
        self.assertIn("0", output)

    def test_zero_countries_hidden_by_default(self):
        with patch(
            f"{COMMAND}.load_country_counts", return_value={"VN": 12}
        ):
            output = self._run("Indo-China")

        self.assertNotIn("Laos", output)

    def test_list_prints_available_groups(self):
        with patch(f"{COMMAND}.load_country_counts", return_value={}):
            output = self._run("--list")

        for name in COUNTRY_GROUPS:
            self.assertIn(name, output)

    def test_unknown_group_is_a_command_error(self):
        with (
            patch(f"{COMMAND}.load_country_counts", return_value={}),
            self.assertRaises(CommandError),
        ):
            self._run("Atlantis")

    def test_missing_group_is_a_command_error(self):
        with (
            patch(f"{COMMAND}.load_country_counts", return_value={}),
            self.assertRaises(CommandError),
        ):
            self._run()

    def test_missing_stats_is_a_command_error(self):
        with (
            patch(f"{COMMAND}.load_country_counts", return_value=None),
            self.assertRaises(CommandError),
        ):
            self._run("Europe")


class LoadCountryCountsTests(SimpleTestCase):
    """
    Country counts come from the most recent stored UserStats row
    """

    def test_returns_parsed_json_from_latest_row(self):
        from types import SimpleNamespace

        from knowledge_commons_profiles.newprofile.management.commands import (
            country_group_stats,
        )

        latest = SimpleNamespace(countries='{"GB": 5, "FR": 2}')
        with patch(f"{COMMAND}.UserStats") as stats_model:
            stats_model.objects.order_by.return_value.first.return_value = (
                latest
            )
            counts = country_group_stats.load_country_counts()

        self.assertEqual(counts, {"GB": 5, "FR": 2})

    def test_returns_none_when_no_stats_row(self):
        from knowledge_commons_profiles.newprofile.management.commands import (
            country_group_stats,
        )

        with patch(f"{COMMAND}.UserStats") as stats_model:
            stats_model.objects.order_by.return_value.first.return_value = (
                None
            )
            counts = country_group_stats.load_country_counts()

        self.assertIsNone(counts)
