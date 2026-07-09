"""
Tests for the MaintenanceMode singleton model and its cached accessors.

Behaviour under test (not implementation): the model exposes the current
maintenance state, mirrors it into the shared cache on save so a toggle takes
effect immediately, and fails open (reports "not in maintenance") when the
cache/database is unreachable so SSO never goes down with it.
"""

from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.test import TestCase

from knowledge_commons_profiles.cilogon.models import MaintenanceMode


class TestMaintenanceModeAccessors(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_is_active_false_when_disabled(self):
        obj = MaintenanceMode.load()
        obj.enabled = False
        obj.save()
        cache.clear()
        self.assertFalse(MaintenanceMode.is_active())

    def test_is_active_true_when_enabled(self):
        obj = MaintenanceMode.load()
        obj.enabled = True
        obj.save()
        cache.clear()
        self.assertTrue(MaintenanceMode.is_active())

    def test_get_state_returns_db_values(self):
        obj = MaintenanceMode.load()
        obj.enabled = True
        obj.title = "Down for now"
        obj.message = "<p>Back soon</p>"
        obj.save()
        cache.clear()
        state = MaintenanceMode.get_state()
        self.assertTrue(state["enabled"])
        self.assertEqual(state["title"], "Down for now")
        self.assertEqual(state["message"], "<p>Back soon</p>")

    def test_save_writes_through_cache(self):
        obj = MaintenanceMode.load()
        obj.enabled = True
        obj.title = "Cached title"
        obj.save()
        # No DB read should be needed: the value is already in the cache.
        cached = cache.get(MaintenanceMode.CACHE_KEY)
        self.assertIsNotNone(cached)
        self.assertTrue(cached["enabled"])
        self.assertEqual(cached["title"], "Cached title")

    def test_only_one_row_ever_exists(self):
        MaintenanceMode.load().save()
        second = MaintenanceMode()
        second.enabled = True
        second.save()
        self.assertEqual(MaintenanceMode.objects.count(), 1)

    def test_is_active_fails_open_on_cache_error(self):
        with patch(
            "knowledge_commons_profiles.cilogon.models.cache.get",
            side_effect=RuntimeError("redis down"),
        ):
            # Even with the cache broken, SSO must not go down: report False.
            self.assertFalse(MaintenanceMode.is_active())

    def test_ais_active_true_when_enabled(self):
        obj = MaintenanceMode.load()
        obj.enabled = True
        obj.save()
        cache.clear()
        self.assertTrue(async_to_sync(MaintenanceMode.ais_active)())

    def test_ais_active_false_when_disabled(self):
        obj = MaintenanceMode.load()
        obj.enabled = False
        obj.save()
        cache.clear()
        self.assertFalse(async_to_sync(MaintenanceMode.ais_active)())
