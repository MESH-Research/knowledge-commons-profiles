"""
Mailchimp functions
"""

import base64
import json
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)

ERROR_THRESHOLD = 400

# ---------------------------------------------------------------------
# Helpers to mimic WordPress behaviour
# ---------------------------------------------------------------------


def trigger_error(message, level="warning"):
    if level == "warning":
        logger.warning(message)
    elif level == "notice":
        logger.info(message)
    else:
        logger.error(message)


def get_user_by_id(user_id: str):
    """
    Lookup profile in Django ORM
    """
    return Profile.objects.get(user_id)


def get_user_member_types(user: Profile):
    """
    Get BuddyPress-like member types.

    Should return list of strings (e.g., ["hc", "mla"]).
    """
    memberships = user.get_external_memberships()

    return [key.lower() for key, value in memberships.items() if value]


# ---------------------------------------------------------------------
# Mailchimp API wrapper (Python version of hcommons_mailchimp_request)
# ---------------------------------------------------------------------


def hcommons_mailchimp_request(endpoint: str, method="GET", params=None):
    if not settings.MAILCHIMP_API_KEY or not settings.MAILCHIMP_DC:
        trigger_error(
            "Mailchimp request failed: Mailchimp constants not defined."
        )
        return None

    params = params or {}

    base = f"https://{settings.MAILCHIMP_DC}.api.mailchimp.com/3.0"
    url = f"{base}{endpoint}"

    if method == "GET":
        body = None
        req_url = url
        if params:
            req_url = f"{url}?{urlencode(params)}"
    else:
        body = json.dumps(params)
        req_url = url

    auth_str = base64.b64encode(
        f"HumanitiesCommons:{settings.MAILCHIMP_API_KEY}".encode()
    ).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json",
    }

    # ruff: noqa: BLE001
    try:
        response = requests.request(
            method=method,
            url=req_url,
            headers=headers,
            data=body,
            timeout=settings.EMAIL_TIMEOUT,
        )
    except Exception as e:
        trigger_error(f"Mailchimp request error: {e!s}")
        return None

    if response.status_code >= ERROR_THRESHOLD:
        trigger_error(f"Mailchimp request error: {response.text}")
        return None

    try:
        return response.json()
    except json.JSONDecodeError:
        trigger_error("Mailchimp request error: invalid JSON in response")
        return None


# ---------------------------------------------------------------------
# Add new user to Mailchimp (Python version of
# hcommons_add_new_user_to_mailchimp)
# ---------------------------------------------------------------------


def hcommons_add_new_user_to_mailchimp(user_id: int, userdata: dict):
    if not (
        settings.MAILCHIMP_LIST_ID
        and settings.MAILCHIMP_API_KEY
        and settings.MAILCHIMP_DC
    ):
        trigger_error(
            "Mailchimp user creation failed: Mailchimp constants not defined."
        )
        return

    if not user_id:
        trigger_error("Mailchimp user creation failed: no user ID provided.")
        return

    try:
        user = get_user_by_id(user_id)
    except NotImplementedError:
        trigger_error("User lookup not implemented")
        return

    if not user:
        trigger_error(
            f"Mailchimp user creation failed: no user found for ID {user_id}"
        )
        return

    # --------------------------------------------------------------
    # TODO: hcommons_set_user_member_types( $user );
    #       (Original PHP)
    #
    # hcommons_set_user_member_types( $user );
    # --------------------------------------------------------------
    # TODO: implement equivalent member-type setting if needed

    if "user_email" not in userdata:
        trigger_error(
            "Mailchimp user creation failed: no email address provided."
        )
        return

    email = userdata["user_email"]

    # Check if Mailchimp already has this user
    existing = hcommons_mailchimp_request(
        f"/lists/{settings.MAILCHIMP_LIST_ID}/members/{email}"
    )

    mailchimp_user_id = ""
    request_method = "POST"

    if isinstance(existing, dict) and "email_address" in existing:
        trigger_error(f"Mailchimp user exists for email {email}", "notice")

        if existing.get("status") == "archived":
            mailchimp_user_id = existing.get("id", "")
            request_method = "PUT"
        else:
            trigger_error(
                f"Mailchimp user exists and is not archived for email {email}",
                "notice",
            )
            return

    # Get member types
    member_types = get_user_member_types(user)
    if not member_types:
        member_types = ["hc"]

    tags = [*member_types, "new-user"]

    # Build request body
    payload = {
        "email_address": email,
        "status": "subscribed",
        "merge_fields": {
            "FNAME": userdata.get("first_name", ""),
            "LNAME": userdata.get("last_name", ""),
            "DNAME": (
                user.display_name if hasattr(user, "display_name") else ""
            ),
            "USERNAME": userdata.get("user_login", ""),
        },
        "tags": tags,
        "interests": {settings.MAILCHIMP_NEWSLETTER_GROUP_ID: True},
    }

    response = hcommons_mailchimp_request(
        f"/lists/{settings.MAILCHIMP_LIST_ID}/members/{mailchimp_user_id}",
        request_method,
        payload,
    )

    if isinstance(response, dict) and "id" in response:
        trigger_error(
            f"Mailchimp user created for email {email} with status "
            f"{response.get('status')}",
            "notice",
        )
    else:
        trigger_error(
            f"Mailchimp user creation failed. Response: {response}",
            "warning",
        )


# ---------------------------------------------------------------------
# Remove user from Mailchimp (Python version of
# hcommons_remove_user_from_mailchimp)
# ---------------------------------------------------------------------


def hcommons_remove_user_from_mailchimp(user_id: int):
    if not settings.MAILCHIMP_LIST_ID:
        trigger_error(
            "Mailchimp user removal failed: Mailchimp constants not defined."
        )
        return

    try:
        user = get_user_by_id(user_id)
    except NotImplementedError:
        trigger_error("User lookup not implemented")
        return

    if not user:
        trigger_error(
            f"Mailchimp user deletion failed: no user found for ID {user_id}"
        )
        return

    trigger_error(f"Removing user {user.user_login} from Mailchimp.", "notice")

    existing = hcommons_mailchimp_request(
        f"/lists/{settings.MAILCHIMP_LIST_ID}/members/{user.user_email}"
    )

    if isinstance(existing, dict) and "email_address" in existing:
        mailchimp_user_id = existing.get("id")

        response = hcommons_mailchimp_request(
            f"/lists/{settings.MAILCHIMP_LIST_ID}/members/{mailchimp_user_id}",
            "DELETE",
            {},
        )

        if response is not None:
            trigger_error(
                f"Mailchimp user deleted for email {user.user_email}", "notice"
            )
        else:
            trigger_error(
                f"Mailchimp user deletion failed. Response: {response}",
                "warning",
            )
    else:
        trigger_error(
            f"Mailchimp deletion failed: user does not exist "
            f"for email {user.user_email}",
            "notice",
        )
