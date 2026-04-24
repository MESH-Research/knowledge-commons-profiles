"""
Tests for ARLISNA pydantic model parsing, especially the Awards and
Committees fields that can contain either empty lists or dict entries
returned by the live API.
"""

from __future__ import annotations

import json

from django.test import SimpleTestCase
from pydantic import TypeAdapter

from knowledge_commons_profiles.cilogon.sync_apis.arlisna import MemberResult
from knowledge_commons_profiles.cilogon.sync_apis.arlisna import (
    MembersSearchResponse,
)


def _minimal_member(**overrides) -> dict:
    """Build a minimal valid MemberResult payload."""
    base = {
        "UniqueID": "abc123",
        "Awards": [],
        "Committees": [],
    }
    base.update(overrides)
    return base


def _wrap(results: list[dict]) -> bytes:
    return json.dumps(
        {"TotalCount": len(results), "Results": results}
    ).encode()


class AwardsParsingTests(SimpleTestCase):
    def test_empty_awards_list_parses(self):
        payload = _wrap([_minimal_member()])
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        self.assertEqual(result.TotalCount, 1)
        self.assertEqual(result.Results[0].Awards, [])

    def test_award_dict_entries_parse(self):
        """Production data has Awards as list of {Name, Year} dicts."""
        payload = _wrap(
            [
                _minimal_member(
                    Awards=[
                        {
                            "Name": "Celine Palatsky Memorial Award",
                            "Year": "2021",
                        },
                        {
                            "Name": "Kress Foundation Award for SEI",
                            "Year": "2021",
                        },
                        {
                            "Name": "Conference Attendance Award",
                            "Year": "2025",
                        },
                    ]
                )
            ]
        )
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        awards = result.Results[0].Awards
        self.assertEqual(len(awards), 3)
        self.assertEqual(awards[0].Name, "Celine Palatsky Memorial Award")
        self.assertEqual(awards[0].Year, "2021")
        self.assertEqual(awards[2].Name, "Conference Attendance Award")
        self.assertEqual(awards[2].Year, "2025")

    def test_award_dict_missing_optional_fields(self):
        payload = _wrap(
            [_minimal_member(Awards=[{"Name": "Solo Award"}])]
        )
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        awards = result.Results[0].Awards
        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0].Name, "Solo Award")
        self.assertIsNone(awards[0].Year)


class CommitteesParsingTests(SimpleTestCase):
    def test_empty_committees_list_parses(self):
        payload = _wrap([_minimal_member()])
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        self.assertEqual(result.Results[0].Committees, [])

    def test_committee_dict_entries_parse(self):
        """Production data has Committees as list of dicts with
        CommitteeMemberUniqueID and end-date fields."""
        payload = _wrap(
            [
                _minimal_member(
                    Committees=[
                        {
                            "CommitteeMemberUniqueID": "cm-xyz-1",
                            "CommitteeName": "Executive Board",
                            "EndDate": "2026-06-30T00:00:00-05:00",
                        }
                    ]
                )
            ]
        )
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        committees = result.Results[0].Committees
        self.assertEqual(len(committees), 1)
        self.assertEqual(
            committees[0].CommitteeMemberUniqueID, "cm-xyz-1"
        )

    def test_committee_dict_ignores_unknown_fields(self):
        payload = _wrap(
            [
                _minimal_member(
                    Committees=[
                        {
                            "CommitteeMemberUniqueID": "id-1",
                            "SomeUnexpectedField": "ignored",
                        }
                    ]
                )
            ]
        )
        adapter = TypeAdapter(MembersSearchResponse)

        result = adapter.validate_json(payload)

        committees = result.Results[0].Committees
        self.assertEqual(committees[0].CommitteeMemberUniqueID, "id-1")


class RegressionTests(SimpleTestCase):
    def test_full_response_with_mixed_awards_and_committees(self):
        """The exact production-shaped payload that triggered the
        ValidationError should now parse successfully."""
        payload = _wrap(
            [
                _minimal_member(
                    Awards=[
                        {"Name": "Celine Palatsky Award", "Year": "2021"},
                        {
                            "Name": "Kress Foundation Award for SEI",
                            "Year": "2021",
                        },
                        {
                            "Name": "Conference Attendance Award",
                            "Year": "2025",
                        },
                    ],
                    Committees=[
                        {
                            "CommitteeMemberUniqueID": "cm-abc",
                            "EndDate": "2026-06-30T00:00:00-05:00",
                        }
                    ],
                )
            ]
        )

        adapter = TypeAdapter(MembersSearchResponse)
        result = adapter.validate_json(payload)

        self.assertEqual(result.TotalCount, 1)
        member: MemberResult = result.Results[0]
        self.assertEqual(len(member.Awards), 3)
        self.assertEqual(len(member.Committees), 1)
