"""
Tests for CILogonConfig startup hooks.

Specifically: the OIDC discovery-document preload (#594). Authlib does
not fetch the discovery document at register() time; it lazy-loads on
first use. We move that fetch to worker startup so the cold cost lands
in boot time, not on whichever unlucky user request happens first.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock
from unittest.mock import patch

from django.test import SimpleTestCase
from django.test import override_settings


@override_settings(CILOGON_PRELOAD_METADATA=True)
class PreloadOidcMetadataTests(SimpleTestCase):
    """The helper invoked by CILogonConfig.ready() at worker startup."""

    def test_calls_load_server_metadata_on_cilogon_client(self):
        from knowledge_commons_profiles.cilogon.apps import (
            _preload_oidc_metadata,
        )

        mock_client = MagicMock()
        with patch(
            "knowledge_commons_profiles.cilogon.oauth.oauth.create_client",
            return_value=mock_client,
        ) as create_client:
            _preload_oidc_metadata()

        create_client.assert_called_once_with("cilogon")
        mock_client.load_server_metadata.assert_called_once_with()

    def test_silently_skips_when_create_client_returns_none(self):
        from knowledge_commons_profiles.cilogon.apps import (
            _preload_oidc_metadata,
        )

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.oauth.create_client",
            return_value=None,
        ):
            # Must not raise.
            _preload_oidc_metadata()

    def test_swallows_exception_and_logs_warning(self):
        from knowledge_commons_profiles.cilogon.apps import (
            _preload_oidc_metadata,
        )

        mock_client = MagicMock()
        mock_client.load_server_metadata.side_effect = RuntimeError("boom")

        with (
            patch(
                "knowledge_commons_profiles.cilogon.oauth.oauth.create_client",
                return_value=mock_client,
            ),
            self.assertLogs(
                "knowledge_commons_profiles.cilogon.apps",
                level=logging.WARNING,
            ) as logs,
        ):
            # Must not propagate.
            _preload_oidc_metadata()

        self.assertTrue(
            any("preload" in record.lower() for record in logs.output),
            msg=f"Expected a warning mentioning preload; got: {logs.output}",
        )


class PreloadOidcMetadataGateTests(SimpleTestCase):
    """The CILOGON_PRELOAD_METADATA setting must short-circuit the
    preload so tests / local dev stay hermetic."""

    @override_settings(CILOGON_PRELOAD_METADATA=False)
    def test_setting_false_skips_oauth_call(self):
        from knowledge_commons_profiles.cilogon.apps import (
            _preload_oidc_metadata,
        )

        with patch(
            "knowledge_commons_profiles.cilogon.oauth.oauth.create_client"
        ) as create_client:
            _preload_oidc_metadata()

        create_client.assert_not_called()


class CILogonConfigReadyTests(SimpleTestCase):
    """The ready() hook must invoke the preload helper."""

    def test_ready_invokes_preload(self):
        from knowledge_commons_profiles.cilogon.apps import CILogonConfig

        with patch(
            "knowledge_commons_profiles.cilogon.apps._preload_oidc_metadata"
        ) as preload:
            config = CILogonConfig.create("knowledge_commons_profiles.cilogon")
            config.ready()

        preload.assert_called_once_with()
