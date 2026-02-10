"""
Utility functions
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

import requests
from django.conf import settings
from nameparser import HumanName
from rest_framework.status import HTTP_400_BAD_REQUEST

from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)

LOGOUT_TIMEOUT = 5


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


def logout_all_endpoints_sync(username="", request=None):
    """Synchronous logout using threading for parallel requests."""

    endpoints = getattr(settings, "LOGOUT_ENDPOINTS", [])
    if not endpoints:
        return []

    headers = {
        "Authorization": f"Bearer {settings.STATIC_API_BEARER}",
        "Content-Type": "application/json",
    }

    username = (
        request.user.username if request and username == "" else username
    )

    def send_request(endpoint):
        msg = f"Sending logout request to {endpoint} for {username}"
        logger.info(msg)
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                params={"username": username},
                timeout=LOGOUT_TIMEOUT,
            )
        except Exception as e:
            msg = f"Error sending logout signal to {endpoint} for {username}"
            logger.exception(msg)
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


def get_external_memberships(obj: Profile, api_only=False):
    """
    Check if a user is a member of an external organisation
    """
    if not obj or not obj.username:
        return {}

    try:
        # Handle case where is_member_of might be None or empty
        member_data = obj.is_member_of
        if not member_data:
            return {}

        member_json = json.loads(member_data)

        if not api_only:
            for role in obj.role_overrides:
                member_json[role] = True

    except (json.JSONDecodeError, AttributeError, Exception) as e:
        message = (
            f"Failed to get external sync memberships "
            f"for {obj.username}: {e}"
        )
        if logger:
            logger.warning(message)
        return {}
    else:
        return member_json
