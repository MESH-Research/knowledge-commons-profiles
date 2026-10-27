"""
Tests for the install_ror management command
"""

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.test import TestCase

from knowledge_commons_profiles.newprofile.management.commands import (
    install_ror,
)
from knowledge_commons_profiles.newprofile.models import RORRecord

INSTALL_ROR = (
    "knowledge_commons_profiles.newprofile.management.commands.install_ror"
)


def _v2_entry(  # noqa: PLR0913
    ror_id="https://ror.org/02d439m40",
    display="University Mental Health Research Institute",
    country="GR",
    lat=37.98376,
    lng=23.72784,
    grid="grid.1088.1",
):
    return {
        "id": ror_id,
        "names": [
            {"value": "UMHRI", "types": ["acronym"], "lang": None},
            {"value": display, "types": ["ror_display", "label"], "lang": "en"},
        ],
        "locations": [
            {
                "geonames_id": 264371,
                "geonames_details": {
                    "country_code": country,
                    "country_name": "Greece",
                    "lat": lat,
                    "lng": lng,
                    "name": "Athens",
                },
            }
        ],
        "external_ids": [
            {"type": "grid", "all": [grid], "preferred": grid},
            {"type": "isni", "all": ["0000 0004 0622 6844"], "preferred": None},
        ],
        "status": "active",
        "types": ["education"],
    }


def _v1_entry():
    return {
        "id": "https://ror.org/01abc2345",
        "name": "Old Schema University",
        "country": {"country_code": "GB", "country_name": "United Kingdom"},
        "addresses": [{"lat": 51.5, "lng": -0.12}],
        "external_ids": {"GRID": {"preferred": "grid.1.1", "all": "grid.1.1"}},
    }


class ParseRorEntryTests(SimpleTestCase):
    def test_v2_uses_ror_display_name(self):
        parsed = install_ror.parse_ror_entry(_v2_entry())

        self.assertEqual(
            parsed["institution_name"],
            "University Mental Health Research Institute",
        )

    def test_v2_reads_id_country_coordinates_and_grid(self):
        parsed = install_ror.parse_ror_entry(_v2_entry())

        self.assertEqual(parsed["ror_id"], "https://ror.org/02d439m40")
        self.assertEqual(parsed["country"], "GR")
        self.assertEqual(parsed["lat"], 37.98376)
        self.assertEqual(parsed["lon"], 23.72784)
        self.assertEqual(parsed["grid_id"], "grid.1088.1")

    def test_v2_without_ror_display_falls_back_to_label(self):
        entry = _v2_entry()
        entry["names"] = [
            {"value": "ACR", "types": ["acronym"], "lang": None},
            {"value": "Label Name", "types": ["label"], "lang": "en"},
        ]

        parsed = install_ror.parse_ror_entry(entry)

        self.assertEqual(parsed["institution_name"], "Label Name")

    def test_v2_without_locations_has_no_country_and_zero_coordinates(self):
        entry = _v2_entry()
        entry["locations"] = []

        parsed = install_ror.parse_ror_entry(entry)

        self.assertIsNone(parsed["country"])
        self.assertEqual(parsed["lat"], 0)
        self.assertEqual(parsed["lon"], 0)

    def test_v2_without_grid_has_no_grid_id(self):
        entry = _v2_entry()
        entry["external_ids"] = [
            {"type": "isni", "all": ["0000"], "preferred": None}
        ]

        parsed = install_ror.parse_ror_entry(entry)

        self.assertIsNone(parsed["grid_id"])

    def test_v2_grid_falls_back_to_first_of_all_when_no_preferred(self):
        entry = _v2_entry()
        entry["external_ids"] = [
            {"type": "grid", "all": ["grid.9.9"], "preferred": None}
        ]

        parsed = install_ror.parse_ror_entry(entry)

        self.assertEqual(parsed["grid_id"], "grid.9.9")

    def test_v1_entries_still_parse(self):
        parsed = install_ror.parse_ror_entry(_v1_entry())

        self.assertEqual(parsed["ror_id"], "https://ror.org/01abc2345")
        self.assertEqual(parsed["institution_name"], "Old Schema University")
        self.assertEqual(parsed["country"], "GB")
        self.assertEqual(parsed["lat"], 51.5)
        self.assertEqual(parsed["lon"], -0.12)
        self.assertEqual(parsed["grid_id"], "grid.1.1")


class SelectDataFileTests(SimpleTestCase):
    def test_prefers_json_over_csv(self):
        chosen = install_ror.select_data_file(
            ["v2.15-2026-10-20-ror-data.csv", "v2.15-2026-10-20-ror-data.json"]
        )

        self.assertEqual(chosen, "v2.15-2026-10-20-ror-data.json")

    def test_prefers_schema_v2_file_in_a_mixed_dump(self):
        chosen = install_ror.select_data_file(
            [
                "v1.63-2024-12-11-ror-data.json",
                "v1.63-2024-12-11-ror-data_schema_v2.json",
            ]
        )

        self.assertEqual(chosen, "v1.63-2024-12-11-ror-data_schema_v2.json")

    def test_single_json_file_is_chosen(self):
        chosen = install_ror.select_data_file(["v1.40-ror-data.json"])

        self.assertEqual(chosen, "v1.40-ror-data.json")

    def test_raises_when_no_json_file(self):
        with self.assertRaises(ValueError):
            install_ror.select_data_file(["ror-data.csv"])


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _fake_requests_get(zip_content: bytes):
    """
    Build a requests.get stand-in: first call returns the Zenodo record
    listing, the second returns the zip archive
    """
    meta = {
        "hits": {
            "hits": [
                {
                    "files": [
                        {
                            "key": "v2.15-2026-10-20-ror-data.zip",
                            "links": {"self": "https://zenodo.example/zip"},
                        }
                    ]
                }
            ]
        }
    }

    def _get(url, timeout=None):
        if "zip" in url:
            return SimpleNamespace(
                content=zip_content, status_code=200, close=lambda: None
            )
        return SimpleNamespace(
            json=lambda: meta, status_code=200, close=lambda: None
        )

    return _get


class InstallRorCommandTests(TestCase):
    def _run(self, files: dict[str, bytes]):
        with patch(
            f"{INSTALL_ROR}.requests.get",
            side_effect=_fake_requests_get(_zip_bytes(files)),
        ):
            call_command("install_ror")

    def test_imports_schema_v2_dump(self):
        entries = [
            _v2_entry(),
            _v2_entry(
                ror_id="https://ror.org/zzz999",
                display="Second University",
                country="US",
                lat=40.7,
                lng=-74.0,
                grid=None,
            ),
        ]
        files = {
            "v2.15-2026-10-20-ror-data.json": json.dumps(entries).encode(),
            "v2.15-2026-10-20-ror-data.csv": b"id,name\n",
        }

        self._run(files)

        self.assertEqual(RORRecord.objects.count(), 2)
        first = RORRecord.objects.get(ror_id="https://ror.org/02d439m40")
        self.assertEqual(
            first.institution_name,
            "University Mental Health Research Institute",
        )
        self.assertEqual(first.country, "GR")
        self.assertAlmostEqual(first.lat, 37.98376)
        self.assertAlmostEqual(first.lon, 23.72784)
        self.assertEqual(first.grid_id, "grid.1088.1")

        second = RORRecord.objects.get(ror_id="https://ror.org/zzz999")
        self.assertEqual(second.country, "US")

    def test_imports_when_csv_is_listed_before_json(self):
        files = {
            "v2.15-2026-10-20-ror-data.csv": b"id,name\n",
            "v2.15-2026-10-20-ror-data.json": json.dumps(
                [_v2_entry()]
            ).encode(),
        }

        self._run(files)

        self.assertEqual(RORRecord.objects.count(), 1)

    def test_replaces_existing_records(self):
        RORRecord.objects.create(
            ror_id="https://ror.org/stale", institution_name="Stale"
        )
        files = {
            "v2.15-2026-10-20-ror-data.json": json.dumps(
                [_v2_entry()]
            ).encode(),
        }

        self._run(files)

        self.assertFalse(RORRecord.objects.filter(ror_id__contains="stale"))
        self.assertEqual(RORRecord.objects.count(), 1)

    def test_imports_a_v1_dump(self):
        files = {
            "v1.63-2024-12-11-ror-data.json": json.dumps(
                [_v1_entry()]
            ).encode(),
        }

        self._run(files)

        record = RORRecord.objects.get()
        self.assertEqual(record.institution_name, "Old Schema University")
        self.assertEqual(record.country, "GB")

    def test_imports_many_entries(self):
        entries = [
            _v2_entry(ror_id=f"https://ror.org/{i:08d}", display=f"Uni {i}")
            for i in range(2500)
        ]
        files = {
            "v2.15-2026-10-20-ror-data.json": json.dumps(entries).encode()
        }

        self._run(files)

        self.assertEqual(RORRecord.objects.count(), 2500)
