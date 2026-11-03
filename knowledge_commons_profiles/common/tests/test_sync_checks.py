"""
``sync_status`` reports, per sync class, whether its required settings are
all set. It is what the health check page shows to superusers.
"""

from __future__ import annotations

from django.test import SimpleTestCase
from django.test import override_settings

from knowledge_commons_profiles.common.sync_checks import sync_status

ALL_SET = {
    "UP_ECA_CONSUMER_KEY": "key",
    "UP_ECA_CONSUMER_SECRET": "secret",
    "MLA_API_KEY": "key",
    "MLA_API_SECRET": "secret",
}


class SyncStatusTests(SimpleTestCase):
    @override_settings(**ALL_SET)
    def test_all_true_when_everything_set(self):
        self.assertEqual(sync_status(), {"UP": True, "MLA": True})

    @override_settings(**{**ALL_SET, "UP_ECA_CONSUMER_KEY": ""})
    def test_up_false_when_up_key_missing(self):
        self.assertEqual(sync_status(), {"UP": False, "MLA": True})

    @override_settings(**{**ALL_SET, "UP_ECA_CONSUMER_SECRET": ""})
    def test_up_false_when_up_secret_missing(self):
        self.assertEqual(sync_status(), {"UP": False, "MLA": True})

    @override_settings(**{**ALL_SET, "MLA_API_KEY": ""})
    def test_mla_false_when_mla_key_missing(self):
        self.assertEqual(sync_status(), {"UP": True, "MLA": False})

    @override_settings(**{**ALL_SET, "MLA_API_SECRET": ""})
    def test_mla_false_when_mla_secret_missing(self):
        self.assertEqual(sync_status(), {"UP": True, "MLA": False})

    @override_settings(
        UP_ECA_CONSUMER_KEY="",
        UP_ECA_CONSUMER_SECRET="",
        MLA_API_KEY="",
        MLA_API_SECRET="",
    )
    def test_all_false_when_nothing_set(self):
        self.assertEqual(sync_status(), {"UP": False, "MLA": False})

    @override_settings(**ALL_SET)
    def test_reports_exactly_the_classes_with_credential_requirements(self):
        self.assertEqual(set(sync_status()), {"UP", "MLA"})
