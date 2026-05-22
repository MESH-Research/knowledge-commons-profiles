import logging

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def _preload_oidc_metadata():
    """
    Force authlib to fetch CILogon's discovery document at worker
    startup so the cold cost lands in boot time, not on whichever user
    request happens to be first after a spawn / restart (#594).

    Any failure here is logged and swallowed — authlib will retry
    lazily on first request as it would have done without this hook.
    Gated by ``CILOGON_PRELOAD_METADATA`` so tests and local dev can
    skip the boot-time HTTP call to cilogon.org.
    """
    # Imported lazily because apps.py is loaded before the app registry
    # is ready, and cilogon.oauth pulls in django.contrib.auth models.
    from django.conf import settings

    if not getattr(settings, "CILOGON_PRELOAD_METADATA", True):
        return

    from knowledge_commons_profiles.cilogon.oauth import oauth

    try:
        client = oauth.create_client("cilogon")
        if client is None:
            return
        client.load_server_metadata()
    except Exception:  # noqa: BLE001 — preload is best-effort
        logger.warning(
            "Could not preload CILogon discovery metadata at startup; "
            "first request after spawn will fetch it instead",
            exc_info=True,
        )


class CILogonConfig(AppConfig):
    name = "knowledge_commons_profiles.cilogon"
    label = "cilogon"
    verbose_name = _("CILogon")

    def ready(self):
        from knowledge_commons_profiles.cilogon import signals  # noqa: F401

        _preload_oidc_metadata()
