"""Load-test scaffolding app.

Activated only when `config.settings.loadtest` is the active settings module.
Its sole job is to monkey-patch outbound integrations so load-test runs
exercise the IDMS in isolation, without hitting Mailchimp, MLA, ARLISNA, UP,
ROR, or the IDMS event API.
"""

from __future__ import annotations

import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _noop(*args, **kwargs):
    return None


def _install_external_sync_stub() -> None:
    from knowledge_commons_profiles.rest_api import sync as sync_module

    sync_module.ExternalSync.sync = staticmethod(_noop)
    logger.warning(
        "loadtest_app: ExternalSync.sync stubbed; no third-party calls "
        "(Mailchimp/MLA/ARLISNA/UP/ROR) will fire during this run.",
    )


def _install_idms_api_stub() -> None:
    from knowledge_commons_profiles.rest_api import idms_api

    class _StubAPIClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            return _noop

    idms_api.APIClient = _StubAPIClient
    logger.warning(
        "loadtest_app: rest_api.idms_api.APIClient replaced with a no-op stub.",
    )


def _install_oidc_callback_diagnostics() -> None:
    """Wrap Authlib's authorize_access_token + IDMS store_session_variables
    so we can see, in the logs, exactly what came back from the mock and
    why a userinfo dict might end up empty. Activated via LOADTEST_DEBUG_OIDC=1.
    """
    from knowledge_commons_profiles.cilogon import oauth as cilogon_oauth

    original_store = cilogon_oauth.store_session_variables

    def wrapped_store(request, token):
        token_keys = sorted(token.keys()) if isinstance(token, dict) else None
        userinfo_in_token = (
            isinstance(token, dict) and isinstance(token.get("userinfo"), dict)
        )
        # Look up the state_data Authlib stored on /login so we can see whether
        # nonce was preserved across the redirect.
        state = request.GET.get("state", "")
        state_key = f"_state_cilogon_{state}"
        state_envelope = request.session.get(state_key)
        state_data = (
            state_envelope.get("data")
            if isinstance(state_envelope, dict)
            else None
        )
        logger.warning(
            "loadtest OIDC debug: token_keys=%s userinfo_present=%s "
            "state_data_keys=%s nonce_in_state_data=%s id_token_in_token=%s",
            token_keys,
            userinfo_in_token,
            sorted(state_data.keys()) if isinstance(state_data, dict) else None,
            isinstance(state_data, dict) and "nonce" in state_data,
            isinstance(token, dict) and "id_token" in token,
        )
        return original_store(request, token)

    cilogon_oauth.store_session_variables = wrapped_store
    logger.warning("loadtest_app: OIDC callback diagnostic wrapper installed.")


class LoadTestAppConfig(AppConfig):
    name = "knowledge_commons_profiles.loadtest_app"
    label = "loadtest_app"
    verbose_name = "Load Test Scaffolding"

    def ready(self) -> None:
        if os.environ.get("LOADTEST_STUB_EXTERNAL_SYNC", "1") == "1":
            _install_external_sync_stub()
        if os.environ.get("LOADTEST_STUB_IDMS_API", "1") == "1":
            _install_idms_api_stub()
        if os.environ.get("LOADTEST_DEBUG_OIDC", "0") == "1":
            _install_oidc_callback_diagnostics()
