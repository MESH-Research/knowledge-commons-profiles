"""WordPress synchronization for profile data (#392)."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def sync_avatar_to_wordpress(username: str, image_url: str) -> bool:
    """Sync the user's avatar to WordPress via REST API.

    Sends the avatar image URL to WordPress so that the user's avatar
    is updated across all WordPress-backed UI surfaces.

    Returns True on success, False on failure or missing configuration.
    """
    url = settings.WORDPRESS_AVATAR_UPDATE_URL
    bearer = settings.STATIC_API_BEARER
    debug = settings.DEBUG

    if debug:
        logger.debug(
            "Avatar sync initiated for user %s, image_url=%s, "
            "target=%s",
            username,
            image_url,
            url or "(not configured)",
        )

    if not url:
        logger.warning("WORDPRESS_AVATAR_UPDATE_URL is not configured")
        return False

    if not bearer:
        logger.warning("STATIC_API_BEARER is not configured")
        return False

    if debug:
        logger.debug(
            "Sending avatar sync POST to %s for user %s", url, username
        )

    try:
        response = requests.post(
            url,
            json={"username": username, "image_url": image_url},
            headers={
                "Authorization": f"Bearer {bearer}",
                "x-auth": bearer,
            },
            timeout=10,
        )
        if debug:
            logger.debug(
                "Avatar sync response for %s: status=%s, body=%s",
                username,
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        logger.exception(
            "Avatar sync connection failed for user %s: "
            "could not connect to %s",
            username,
            url,
        )
        return False
    except requests.exceptions.Timeout:
        logger.exception(
            "Avatar sync timed out for user %s: %s did not respond "
            "within 10 seconds",
            username,
            url,
        )
        return False
    except requests.exceptions.RequestException:
        logger.exception(
            "Failed to sync avatar to WordPress for user %s", username
        )
        return False

    logger.info("Synced avatar for %s to WordPress", username)
    return True
