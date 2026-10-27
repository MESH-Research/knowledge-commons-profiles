"""
Startup check: are the External Client App credentials present?

Missing credentials make every UP lookup report "no contact" without any
exception reaching users, so the only visible symptom is members losing
their UP badge. On deployments that opt in (production), report the gap to
Sentry at startup. Never raise: a misconfigured sync must not stop the
application from serving.
"""

from __future__ import annotations

import logging

import sentry_sdk
from django.conf import settings

from knowledge_commons_profiles.up_salesforce.sync import SYNC_KEY

logger = logging.getLogger(__name__)

CREDENTIAL_SETTINGS = ("UP_ECA_CONSUMER_KEY", "UP_ECA_CONSUMER_SECRET")


def missing_credentials() -> list[str]:
    """Names of the UP_ECA_* credential settings that are empty."""
    return [
        name for name in CREDENTIAL_SETTINGS if not getattr(settings, name, "")
    ]


def _up_sync_is_active() -> bool:
    return any(
        class_name == SYNC_KEY
        for class_name, _organizations in settings.EXTERNAL_SYNC_CLASSES
    )


def report_missing_credentials() -> list[str]:
    """
    Send one Sentry event naming the missing settings when the deployment
    requires them and UP is an active sync class. Returns the names that
    were reported (empty when nothing was reported).
    """
    if not getattr(settings, "UP_ECA_REQUIRE_CREDENTIALS", False):
        return []
    if not _up_sync_is_active():
        return []

    missing = missing_credentials()
    if not missing:
        return []

    message = (
        "UP Salesforce External Client App credentials are not configured: "
        + ", ".join(missing)
        + ". Every UP membership lookup will report no contact until they "
        "are set."
    )
    logger.error(message)
    try:
        sentry_sdk.capture_message(message, level="error")
    except Exception:
        logger.exception("Could not report missing UP credentials to Sentry")
    return missing
