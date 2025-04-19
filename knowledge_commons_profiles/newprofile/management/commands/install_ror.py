"""
(c) ΔQ Programming LLP, 2021
This program is free software; you may redistribute and/or modify
it under the terms of the Apache License v2.0.
"""

import contextlib
import io
import json
import logging
import tempfile
import zipfile
from contextlib import closing

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import RORRecord

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    A management command that fetches and installs the latest ROR support
    """

    help = "Installs ROR functionality"

    @transaction.atomic
    def handle(self, *args, **options):
        # download the latest ROR file from Zenodo
        url = (
            "https://zenodo.org/api/records/"
            "?communities=ror-data&sort=mostrecent"
        )

        # the meta response is the JSON from Zenodo that specifies the latest
        # version
        meta_response = requests.get(url, timeout=settings.ZENODO_TIMEOUT)
        latest_url = meta_response.json()["hits"]["hits"][0]["files"][0][
            "links"
        ]["self"]

        # this downloads and unzips the latest ROR file to a temp JSON file
        # when this context processor closes, the temporary files will be
        # deleted
        logger.info("Downloading ROR records")
        with tempfile.NamedTemporaryFile(suffix=".json") as temp_output:
            zip_file = requests.get(
                latest_url, timeout=settings.ZENODO_TIMEOUT
            )

            logger.info("Extracting ROR JSON")

            with (
                closing(zip_file),
                zipfile.ZipFile(io.BytesIO(zip_file.content)) as archive,
            ):
                temp_output.write(archive.read(archive.infolist()[0]))

            # now we have the JSON file at temp_output
            temp_output.seek(0)
            ror_json = json.loads(temp_output.read())

        # delete existing records
        logger.info("Deleting existing records")
        RORRecord.objects.all().delete()

        logger.info("Importing")

        # Parse ROR JSON
        for entry in track(ror_json):
            ror_id = entry["id"]
            ror_name = entry["name"]
            ror_country = entry["country"]["country_code"]
            try:
                grid_id = (
                    entry["external_ids"]
                    .get("GRID", {})
                    .get("preferred", None)
                )
            except KeyError:
                grid_id = None

            lat = 0
            lon = 0

            if "addresses" in entry:
                with contextlib.suppress(KeyError):
                    lat = entry["addresses"][0]["lat"]
                    lon = entry["addresses"][0]["lng"]

            ror_record = RORRecord(
                ror_id=ror_id,
                institution_name=ror_name,
                country=ror_country,
                grid_id=grid_id,
                lat=lat,
                lon=lon,
            )
            ror_record.save()

        logger.info("ROR fixtures installed.")
