import logging
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from django.core import mail
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.utils.log import AdminEmailHandler

from knowledge_commons_profiles.newprofile.views.health import health


class TestHealthView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_200_all_healthy(
        self, mock_cache, mock_connections, mock_api_check
    ):
        """Test 200 when all infra and API checks are healthy."""
        mock_api_check.return_value = {
            "https://api1.com/logout": "reachable",
        }
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db

        request = self.factory.get("/health/")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertIn("API Endpoints", data)
        self.assertEqual(
            data["API Endpoints"]["https://api1.com/logout"], "reachable"
        )

    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_500_redis_fails_api_still_present(
        self, mock_cache, mock_connections, mock_api_check
    ):
        """Test 500 when Redis fails but API info is still in response."""
        import redis as redis_lib

        mock_cache.set.side_effect = redis_lib.exceptions.ConnectionError(
            "Redis down"
        )
        mock_api_check.return_value = {
            "https://api1.com/logout": "reachable",
        }
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db

        request = self.factory.get("/health/")
        response = health(request)

        self.assertEqual(response.status_code, 500)
        import json

        data = json.loads(response.content)
        self.assertIn("API Endpoints", data)
        self.assertIn("unhealthy", data["REDIS"])

    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_200_when_api_unreachable(
        self, mock_cache, mock_connections, mock_api_check
    ):
        """API unreachable must NOT cause HTTP 500."""
        mock_api_check.return_value = {
            "https://api1.com/logout": "unreachable: 503",
        }
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db

        request = self.factory.get("/health/")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertEqual(
            data["API Endpoints"]["https://api1.com/logout"],
            "unreachable: 503",
        )

    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_no_endpoints_configured(
        self, mock_cache, mock_connections, mock_api_check
    ):
        """Test that empty endpoints means no API Endpoints key."""
        mock_api_check.return_value = {}
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db

        request = self.factory.get("/health/")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertNotIn("API Endpoints", data)

    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_api_check_exception_does_not_crash(
        self, mock_cache, mock_connections, mock_api_check
    ):
        """Health endpoint must not crash if API check raises."""
        mock_api_check.side_effect = RuntimeError("Unexpected error")
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db

        request = self.factory.get("/health/")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        import json

        data = json.loads(response.content)
        self.assertIn("API Endpoints", data)
        self.assertIn("check failed", data["API Endpoints"])


class TestHealthAdminEmails(TestCase):
    """Regression tests for the /health/ admin-email flood (issue #561).

    Errors at /health/ must not produce admin emails; Sentry is the sole
    error-notification channel.
    """

    def test_django_request_logger_has_no_admin_email_handler(self):
        request_logger = logging.getLogger("django.request")
        reachable = []
        current = request_logger
        while current is not None:
            reachable.extend(current.handlers)
            if not current.propagate:
                break
            current = current.parent

        admin_handlers = [
            h for h in reachable if isinstance(h, AdminEmailHandler)
        ]
        self.assertEqual(
            admin_handlers,
            [],
            "django.request must not reach AdminEmailHandler "
            f"(found: {admin_handlers}). Rely on Sentry instead.",
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMINS=[("Test Admin", "admin@example.com")],
        DEBUG=False,
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health"
        ".check_api_endpoints_health"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.health.connections"
    )
    @patch("knowledge_commons_profiles.newprofile.views.health.cache")
    def test_health_500_does_not_queue_admin_email(
        self, mock_cache, mock_connections, mock_api_check
    ):
        import redis as redis_lib

        mock_cache.set.side_effect = redis_lib.exceptions.ConnectionError(
            "Redis down"
        )
        mock_db = Mock()
        mock_db.cursor.return_value = Mock()
        mock_connections.__getitem__.return_value = mock_db
        mock_api_check.return_value = {}

        client = Client(raise_request_exception=False)
        mail.outbox = []
        response = client.get("/health/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(mail.outbox), 0)


if __name__ == "__main__":
    unittest.main()
