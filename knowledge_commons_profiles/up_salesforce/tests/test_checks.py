"""
The credential check must report to Sentry on opted-in deployments and
must never prevent the application from starting.
"""

from __future__ import annotations

from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase
from django.test import override_settings

from knowledge_commons_profiles.up_salesforce import checks
from knowledge_commons_profiles.up_salesforce.checks import missing_credentials
from knowledge_commons_profiles.up_salesforce.checks import (
    report_missing_credentials,
)

UP_SYNC = [("UP", ["Association of American University Presses"])]
CONFIGURED = {
    "UP_ECA_CONSUMER_KEY": "key",
    "UP_ECA_CONSUMER_SECRET": "secret",
}


class MissingCredentialsTests(SimpleTestCase):
    @override_settings(**CONFIGURED)
    def test_nothing_missing_when_both_set(self):
        self.assertEqual(missing_credentials(), [])

    @override_settings(UP_ECA_CONSUMER_KEY="", UP_ECA_CONSUMER_SECRET="s")
    def test_key_missing(self):
        self.assertEqual(missing_credentials(), ["UP_ECA_CONSUMER_KEY"])

    @override_settings(UP_ECA_CONSUMER_KEY="k", UP_ECA_CONSUMER_SECRET="")
    def test_secret_missing(self):
        self.assertEqual(missing_credentials(), ["UP_ECA_CONSUMER_SECRET"])

    @override_settings(UP_ECA_CONSUMER_KEY="", UP_ECA_CONSUMER_SECRET="")
    def test_both_missing(self):
        self.assertEqual(
            missing_credentials(),
            ["UP_ECA_CONSUMER_KEY", "UP_ECA_CONSUMER_SECRET"],
        )


@override_settings(
    UP_ECA_REQUIRE_CREDENTIALS=True,
    UP_ECA_CONSUMER_KEY="",
    UP_ECA_CONSUMER_SECRET="",
    EXTERNAL_SYNC_CLASSES=UP_SYNC,
)
class ReportMissingCredentialsTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.object(checks.sentry_sdk, "capture_message")
        self.capture = patcher.start()
        self.addCleanup(patcher.stop)

    def test_reports_both_names_to_sentry_as_an_error(self):
        reported = report_missing_credentials()

        self.assertEqual(
            reported, ["UP_ECA_CONSUMER_KEY", "UP_ECA_CONSUMER_SECRET"]
        )
        self.assertEqual(self.capture.call_count, 1)
        message = self.capture.call_args.args[0]
        self.assertIn("UP_ECA_CONSUMER_KEY", message)
        self.assertIn("UP_ECA_CONSUMER_SECRET", message)
        self.assertEqual(self.capture.call_args.kwargs.get("level"), "error")

    @override_settings(UP_ECA_CONSUMER_KEY="key")
    def test_reports_only_the_missing_name(self):
        reported = report_missing_credentials()
        self.assertEqual(reported, ["UP_ECA_CONSUMER_SECRET"])
        message = self.capture.call_args.args[0]
        self.assertIn("UP_ECA_CONSUMER_SECRET", message)
        self.assertNotIn("UP_ECA_CONSUMER_KEY", message)

    @override_settings(**CONFIGURED)
    def test_silent_when_configured(self):
        self.assertEqual(report_missing_credentials(), [])
        self.capture.assert_not_called()

    @override_settings(UP_ECA_REQUIRE_CREDENTIALS=False)
    def test_silent_when_deployment_does_not_require_credentials(self):
        self.assertEqual(report_missing_credentials(), [])
        self.capture.assert_not_called()

    @override_settings(EXTERNAL_SYNC_CLASSES=[("MLA", ["MLA"])])
    def test_silent_when_up_is_not_an_active_sync_class(self):
        self.assertEqual(report_missing_credentials(), [])
        self.capture.assert_not_called()

    def test_sentry_failure_does_not_propagate(self):
        self.capture.side_effect = RuntimeError("sentry down")
        reported = report_missing_credentials()
        self.assertEqual(
            reported, ["UP_ECA_CONSUMER_KEY", "UP_ECA_CONSUMER_SECRET"]
        )

    def test_app_ready_runs_the_check_without_raising(self):
        apps.get_app_config("up_salesforce").ready()
        self.assertEqual(self.capture.call_count, 1)

    @override_settings(UP_ECA_REQUIRE_CREDENTIALS=False)
    def test_app_ready_is_silent_off_production(self):
        apps.get_app_config("up_salesforce").ready()
        self.capture.assert_not_called()


class RequireCredentialsDefaultTests(SimpleTestCase):
    def test_default_is_off(self):
        from django.conf import settings

        self.assertFalse(settings.UP_ECA_REQUIRE_CREDENTIALS)
