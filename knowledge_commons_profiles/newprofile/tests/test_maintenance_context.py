"""
Tests for the maintenance context processor that surfaces the maintenance
banner state to templates.
"""

from django.core.cache import cache
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.newprofile.context_processors import maintenance


class MaintenanceContextProcessorTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_inactive_by_default(self):
        context = maintenance(self.factory.get("/"))
        self.assertFalse(context["MAINTENANCE_ACTIVE"])

    def test_active_exposes_message(self):
        obj = MaintenanceMode.load()
        obj.enabled = True
        obj.message = "<p>Editing paused</p>"
        obj.save()
        context = maintenance(self.factory.get("/"))
        self.assertTrue(context["MAINTENANCE_ACTIVE"])
        self.assertEqual(
            context["MAINTENANCE_MESSAGE"], "<p>Editing paused</p>"
        )
