"""
Which external sync classes have the settings they need to work?

A sync class whose credentials are missing does not raise: it quietly
reports "no contact" for every lookup, so members lose their badge with no
visible error. The health check page shows this status to superusers.
"""

from __future__ import annotations

from django.conf import settings

from knowledge_commons_profiles.up_salesforce.checks import CREDENTIAL_SETTINGS

# Sync class name -> the settings that must be non-empty for it to work.
REQUIRED_SETTINGS: dict[str, tuple[str, ...]] = {
    "MLA": ("MLA_API_KEY", "MLA_API_SECRET"),
    "UP": CREDENTIAL_SETTINGS,
}


def sync_status() -> dict[str, bool]:
    """
    Per-sync-class status: ``True`` when every setting the class needs is
    set, ``False`` otherwise.
    """
    return {
        class_name: all(getattr(settings, name, "") for name in names)
        for class_name, names in REQUIRED_SETTINGS.items()
    }
