"""
Tests for the match_ror management command
"""

from io import StringIO
from unittest.mock import MagicMock
from unittest.mock import patch

import requests
from django.core.management import CommandError
from django.core.management import call_command
from django.test import SimpleTestCase
from django.test import TestCase

from knowledge_commons_profiles.newprofile.management.commands import match_ror
from knowledge_commons_profiles.newprofile.models import RORLookup
from knowledge_commons_profiles.newprofile.models import RORRecord

MATCH_ROR = (
    "knowledge_commons_profiles.newprofile.management.commands.match_ror"
)


class FakeProfileDataQuerySet:
    """
    In-memory stand-in for the WpProfileData queryset
    """

    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, **kwargs):
        rows = self.rows
        if "field__name" in kwargs:
            rows = [r for r in rows if r["field"] == kwargs["field__name"]]
        return FakeProfileDataQuerySet(rows)

    def exclude(self, **kwargs):
        rows = self.rows
        if "value" in kwargs:
            rows = [r for r in rows if r["value"] != kwargs["value"]]
        if kwargs.get("value__isnull"):
            rows = [r for r in rows if r["value"] is not None]
        return FakeProfileDataQuerySet(rows)

    def values_list(self, field, flat=False):
        return FakeProfileDataQuerySet(
            [{"value": r[field]} for r in self.rows]
        )

    def distinct(self):
        seen = []
        for r in self.rows:
            if r not in seen:
                seen.append(r)
        return FakeProfileDataQuerySet(seen)

    def order_by(self, *fields):
        return FakeProfileDataQuerySet(
            sorted(self.rows, key=lambda r: str(r["value"]))
        )

    def iterator(self, chunk_size=None):
        return iter(self)

    def __iter__(self):
        return iter(r["value"] for r in self.rows)


class DistinctInstitutionsTests(SimpleTestCase):
    def _run(self, rows):
        profile_data = MagicMock()
        profile_data.objects = FakeProfileDataQuerySet(rows)

        with patch(f"{MATCH_ROR}.WpProfileData", profile_data):
            return match_ror.distinct_institutions()

    def test_returns_each_institution_once(self):
        rows = [
            {"field": "Institutional or Other Affiliation", "value": "A"},
            {"field": "Institutional or Other Affiliation", "value": "B"},
            {"field": "Institutional or Other Affiliation", "value": "A"},
        ]

        self.assertEqual(sorted(self._run(rows)), ["A", "B"])

    def test_ignores_other_profile_fields(self):
        rows = [
            {"field": "Institutional or Other Affiliation", "value": "A"},
            {"field": "Title", "value": "Professor"},
        ]

        self.assertEqual(list(self._run(rows)), ["A"])

    def test_ignores_empty_and_blank_values(self):
        rows = [
            {"field": "Institutional or Other Affiliation", "value": "A"},
            {"field": "Institutional or Other Affiliation", "value": ""},
            {"field": "Institutional or Other Affiliation", "value": "   "},
            {"field": "Institutional or Other Affiliation", "value": None},
        ]

        self.assertEqual(list(self._run(rows)), ["A"])


class MatchRorCommandTests(TestCase):
    def setUp(self):
        self.record = RORRecord.objects.create(
            ror_id="https://ror.org/abc123",
            institution_name="University of Testlandia",
            country="TL",
            lat=1.0,
            lon=2.0,
        )

    def _run(self, institutions, lookup=None, **options):
        """
        Run the command with the given institution strings and a fake
        RORLookup.lookup that records what it was asked for
        """
        asked = []

        def _lookup(text):
            asked.append(text)
            if lookup:
                return lookup(text)
            return RORLookup.objects.create(ror=self.record, text=text)

        out = StringIO()

        with (
            patch(
                f"{MATCH_ROR}.distinct_institutions",
                return_value=list(institutions),
            ),
            patch.object(RORLookup, "lookup", side_effect=_lookup),
        ):
            call_command("match_ror", stdout=out, **options)

        return asked, out.getvalue()

    def test_looks_up_every_distinct_institution(self):
        asked, _ = self._run(["Univ A", "Univ B", "Univ C"])

        self.assertEqual(sorted(asked), ["Univ A", "Univ B", "Univ C"])
        self.assertEqual(RORLookup.objects.count(), 3)

    def test_processes_more_than_the_first_institution(self):
        asked, _ = self._run([f"Univ {i}" for i in range(25)])

        self.assertEqual(len(asked), 25)

    def test_skips_institutions_that_already_have_a_lookup(self):
        RORLookup.objects.create(ror=self.record, text="Univ A")

        asked, _ = self._run(["Univ A", "Univ B"])

        self.assertEqual(asked, ["Univ B"])
        self.assertEqual(RORLookup.objects.count(), 2)

    def test_delete_option_clears_existing_lookups_first(self):
        RORLookup.objects.create(ror=self.record, text="Stale")

        asked, _ = self._run(["Univ A"], delete=True)

        self.assertEqual(asked, ["Univ A"])
        self.assertFalse(RORLookup.objects.filter(text="Stale").exists())
        self.assertEqual(RORLookup.objects.count(), 1)

    def test_continues_when_the_ror_api_fails_for_one_institution(self):
        def flaky(text):
            if text == "Univ B":
                msg = "ROR down"
                raise requests.ConnectionError(msg)
            return RORLookup.objects.create(ror=self.record, text=text)

        asked, _ = self._run(["Univ A", "Univ B", "Univ C"], lookup=flaky)

        self.assertEqual(sorted(asked), ["Univ A", "Univ B", "Univ C"])
        self.assertEqual(
            sorted(RORLookup.objects.values_list("text", flat=True)),
            ["Univ A", "Univ C"],
        )

    def test_continues_when_no_match_is_found(self):
        def no_match(text):
            return None

        asked, _ = self._run(["Univ A", "Univ B"], lookup=no_match)

        self.assertEqual(sorted(asked), ["Univ A", "Univ B"])
        self.assertEqual(RORLookup.objects.count(), 0)

    def test_reports_a_summary(self):
        def mixed(text):
            if text == "Univ B":
                return None
            return RORLookup.objects.create(ror=self.record, text=text)

        _, output = self._run(["Univ A", "Univ B"], lookup=mixed)

        self.assertIn("1", output)
        self.assertRegex(output, r"(?i)match")

    def test_refuses_to_run_without_ror_records(self):
        RORRecord.objects.all().delete()

        with (
            patch(
                f"{MATCH_ROR}.distinct_institutions",
                return_value=["Univ A"],
            ),
            patch.object(RORLookup, "lookup") as lookup,
            self.assertRaises(CommandError),
        ):
            call_command("match_ror")

        lookup.assert_not_called()
