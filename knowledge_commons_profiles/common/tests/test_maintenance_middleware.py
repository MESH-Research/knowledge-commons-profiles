"""
Tests for the read-only maintenance middleware and the shared maintenance-page
renderer.

Behaviour under test: when maintenance mode is on, writes by ordinary users are
turned into the maintenance page, reads pass through, staff bypass entirely, and
the admin / health / broker / machine-to-machine endpoints keep accepting
writes so nothing that depends on them breaks.
"""

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.common.middleware import (
    MaintenanceReadOnlyMiddleware,
)
from knowledge_commons_profiles.common.middleware import render_maintenance_page

SENTINEL = "PASSED-THROUGH"


def _passthrough(request):
    return SENTINEL


def _enable_maintenance(title="Down", message="<p>Back soon</p>"):
    obj = MaintenanceMode.load()
    obj.enabled = True
    obj.title = title
    obj.message = message
    obj.save()


class MaintenanceMiddlewareTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = RequestFactory()
        self.mw = MaintenanceReadOnlyMiddleware(_passthrough)
        self.anon = AnonymousUser()
        self.normal = User.objects.create_user("normal", password="x")
        self.staff = User.objects.create_user(
            "staff", password="x", is_staff=True
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _post(self, path, user):
        request = self.factory.post(path)
        request.user = user
        return request

    def _get(self, path, user):
        request = self.factory.get(path)
        request.user = user
        return request

    def test_passes_through_when_not_in_maintenance(self):
        result = self.mw(self._post("/register/", self.anon))
        self.assertEqual(result, SENTINEL)

    def test_read_passes_through_in_maintenance(self):
        _enable_maintenance()
        result = self.mw(self._get("/register/", self.anon))
        self.assertEqual(result, SENTINEL)

    def test_write_blocked_for_anonymous_in_maintenance(self):
        _enable_maintenance()
        result = self.mw(self._post("/register/", self.anon))
        self.assertNotEqual(result, SENTINEL)
        self.assertEqual(result.status_code, 503)

    def test_write_blocked_for_normal_user_in_maintenance(self):
        _enable_maintenance()
        result = self.mw(self._post("/register/", self.normal))
        self.assertEqual(result.status_code, 503)

    def test_staff_bypass_write_in_maintenance(self):
        _enable_maintenance()
        result = self.mw(self._post("/register/", self.staff))
        self.assertEqual(result, SENTINEL)

    def test_unresolvable_write_path_blocked(self):
        _enable_maintenance()
        result = self.mw(self._post("/no/such/path/", self.normal))
        self.assertEqual(result.status_code, 503)

    def test_broker_endpoint_write_allowed(self):
        _enable_maintenance()
        result = self.mw(
            self._post("/broker/verify-nonce/", self.anon)
        )
        self.assertEqual(result, SENTINEL)

    def test_health_write_allowed(self):
        _enable_maintenance()
        result = self.mw(self._post("/health/", self.anon))
        self.assertEqual(result, SENTINEL)

    def test_rest_token_endpoint_write_allowed(self):
        _enable_maintenance()
        result = self.mw(self._post("/api/v1/tokens/", self.anon))
        self.assertEqual(result, SENTINEL)

    def test_admin_write_allowed(self):
        _enable_maintenance()
        result = self.mw(self._post("/admin/", self.staff))
        self.assertEqual(result, SENTINEL)


class RenderMaintenancePageTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_renders_configured_message_with_503(self):
        _enable_maintenance(
            title="Scheduled outage", message="<p>Try later friend</p>"
        )
        request = self.factory.get("/")
        request.user = AnonymousUser()
        response = render_maintenance_page(request)
        self.assertEqual(response.status_code, 503)
        body = response.content.decode()
        self.assertIn("Scheduled outage", body)
        self.assertIn("Try later friend", body)
