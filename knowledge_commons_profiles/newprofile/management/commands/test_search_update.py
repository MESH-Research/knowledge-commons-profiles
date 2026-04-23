"""
A management command to test Mailchimp functions
"""
import logging
from datetime import UTC
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from pydantic import TypeAdapter
from pydantic import ValidationError

from knowledge_commons_profiles.newprofile.cc_search import CCSearchResult
from knowledge_commons_profiles.newprofile.cc_search import (
    build_cc_search_document,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Test Mailchimp"

    def handle(self, *args, **options):

        base_url = settings.CC_SEARCH_URL.rstrip("/")

        url = f"{base_url}/documents"
        method = "POST"

        bearer = settings.CC_SEARCH_ADMIN_KEY

        headers = {
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info("Sending %s request to %s", method, url)

        doc = build_cc_search_document(
            full_name="Martin Paul Eve",
            username="martin_eve",
            about="",
            profile_url="https://profiles.hcommons.org/members/martin_eve",
            other_urls=[
                "https://mla.hcommons.org/members/martin_eve",
            ],
            modified_dt=datetime.now(tz=UTC),
            network_node="hc",
            thumbnail_url="",
            cc_id=""
        )

        payload = doc.model_dump(exclude_none=True)

        timeout = settings.CC_SEARCH_TIMEOUT

        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.exception("Error calling CC search API (%s %s)", method, url)
            return None

        try:
            adapter = TypeAdapter(CCSearchResult)
            parsed = adapter.validate_python(resp.json())
        except ValidationError:
            logger.exception("Error calling CC search API (%s %s)", method, url)
            return None
        except ValueError:
            logger.exception(
                "Error converting CC search API response to JSON (%s %s)",
                method,
                url,
            )
            return None

        try:
            return parsed
        except ValueError:
            logger.exception("CC search API returned non-JSON response")
            return None
