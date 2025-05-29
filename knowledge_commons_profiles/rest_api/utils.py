"""
Utility functions
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

import requests
from django.conf import settings
from nameparser import HumanName
from rest_framework.status import HTTP_400_BAD_REQUEST

from knowledge_commons_profiles.newprofile.models import Profile


def build_metadata(authed, error=None):
    """
    Build the metadata for the response
    """

    return_dict = {
        "meta": {
            "authorized": authed,
        }
    }

    if error:
        return_dict["meta"]["error"] = error

    return return_dict


def get_first_name(obj: Profile, logger) -> str:
    """Extract and format the first name"""
    if not obj.name:
        return ""

    try:
        name = HumanName(obj.name)
        # Include middle if present
        parts = [name.first, name.middle]
        return " ".join(p for p in parts if p).strip()
    except Exception as e:  # noqa: BLE001
        message = f"Failed to parse first name for {obj.username}: {e}"
        logger.warning(message)
        return ""


def get_last_name(obj: Profile, logger) -> str:
    """Extract and format the last name"""
    if not obj.name:
        return ""

    try:
        return HumanName(obj.name).last or ""
    except Exception as e:  # noqa: BLE001
        message = f"Failed to parse last name for {obj.username}: {e}"
        logger.warning(message)
        return ""


def logout_all_endpoints_sync():
    """Synchronous logout using threading for parallel requests."""

    endpoints = getattr(settings, "LOGOUT_ENDPOINTS", [])
    if not endpoints:
        return []

    headers = {
        "Authorization": f"Bearer {settings.STATIC_API_BEARER}",
        "Content-Type": "application/json",
    }

    def send_request(endpoint):
        try:
            response = requests.post(
                endpoint, headers=headers, json={}, timeout=30
            )
        except Exception as e:  # noqa: BLE001
            return {
                "endpoint": endpoint,
                "status": None,
                "success": False,
                "error": str(e),
            }
        else:
            return {
                "endpoint": endpoint,
                "status": response.status_code,
                "success": response.status_code < HTTP_400_BAD_REQUEST,
            }

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_endpoint = {
            executor.submit(send_request, endpoint): endpoint
            for endpoint in endpoints
        }

        return [future.result() for future in as_completed(future_to_endpoint)]
