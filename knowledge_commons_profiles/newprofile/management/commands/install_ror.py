"""
(c) ΔQ Programming LLP, 2021
This program is free software; you may redistribute and/or modify
it under the terms of the Apache License v2.0.
"""

import io
import json
import logging
import zipfile
from contextlib import closing

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import RORRecord

logger = logging.getLogger(__name__)

ZENODO_RECORDS_URL = (
    "https://zenodo.org/api/records/?communities=ror-data&sort=mostrecent"
)
BATCH_SIZE = 1000


def select_data_file(names: list[str]) -> str:
    """
    Choose the ROR JSON data file from the names in a dump archive.

    Current dumps contain a single schema v2 JSON file (plus a CSV). Older
    dumps contained both a v1 JSON file and a "_schema_v2" JSON file, in
    which case the v2 file is preferred.
    """
    json_files = [name for name in names if name.lower().endswith(".json")]

    if not json_files:
        msg = f"No JSON data file found in ROR dump: {names}"
        raise ValueError(msg)

    for name in json_files:
        if "schema_v2" in name.lower():
            return name

    for name in json_files:
        if name.lower().startswith("v2"):
            return name

    return json_files[0]


def _v2_display_name(entry: dict) -> str | None:
    names = entry.get("names") or []

    for wanted in ("ror_display", "label"):
        for name in names:
            if wanted in (name.get("types") or []):
                return name.get("value")

    return names[0].get("value") if names else None


def _v2_grid_id(entry: dict) -> str | None:
    for external in entry.get("external_ids") or []:
        if (external.get("type") or "").lower() != "grid":
            continue

        if external.get("preferred"):
            return external["preferred"]

        all_ids = external.get("all") or []
        return all_ids[0] if all_ids else None

    return None


def _parse_v2(entry: dict) -> dict:
    locations = entry.get("locations") or []
    details = (locations[0].get("geonames_details") or {}) if locations else {}

    return {
        "ror_id": entry["id"],
        "institution_name": _v2_display_name(entry),
        "country": details.get("country_code"),
        "grid_id": _v2_grid_id(entry),
        "lat": details.get("lat") or 0,
        "lon": details.get("lng") or 0,
    }


def _parse_v1(entry: dict) -> dict:
    addresses = entry.get("addresses") or []
    address = addresses[0] if addresses else {}

    external_ids = entry.get("external_ids") or {}
    grid_id = None
    if isinstance(external_ids, dict):
        grid_id = (external_ids.get("GRID") or {}).get("preferred")

    return {
        "ror_id": entry["id"],
        "institution_name": entry.get("name"),
        "country": (entry.get("country") or {}).get("country_code"),
        "grid_id": grid_id,
        "lat": address.get("lat") or 0,
        "lon": address.get("lng") or 0,
    }


def parse_ror_entry(entry: dict) -> dict:
    """
    Map a ROR dump entry (schema v1 or v2) onto RORRecord field values
    """
    if "names" in entry:
        return _parse_v2(entry)

    return _parse_v1(entry)


class Command(BaseCommand):
    """
    A management command that fetches and installs the latest ROR support
    """

    help = "Installs ROR functionality"

    def _latest_dump_url(self) -> str:
        meta_response = requests.get(
            ZENODO_RECORDS_URL, timeout=settings.ZENODO_TIMEOUT
        )
        return meta_response.json()["hits"]["hits"][0]["files"][0]["links"][
            "self"
        ]

    def _download_entries(self) -> list[dict]:
        logger.info("Downloading ROR records")
        zip_response = requests.get(
            self._latest_dump_url(), timeout=settings.ZENODO_TIMEOUT
        )

        logger.info("Extracting ROR JSON")
        with (
            closing(zip_response),
            zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive,
        ):
            data_file = select_data_file(archive.namelist())
            logger.info("Reading %s", data_file)
            return json.loads(archive.read(data_file))

    @transaction.atomic
    def handle(self, *args, **options):
        entries = self._download_entries()

        logger.info("Deleting existing records")
        RORRecord.objects.all().delete()

        logger.info("Importing %s ROR records", len(entries))

        batch: list[RORRecord] = []
        for entry in track(entries, description="Importing ROR"):
            batch.append(RORRecord(**parse_ror_entry(entry)))

            if len(batch) >= BATCH_SIZE:
                RORRecord.objects.bulk_create(batch)
                batch = []

        if batch:
            RORRecord.objects.bulk_create(batch)

        logger.info("ROR fixtures installed.")
