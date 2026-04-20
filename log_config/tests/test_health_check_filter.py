import logging
import unittest

from log_config.health_check_filter import HealthCheckFilter


class TestHealthCheckFilter(unittest.TestCase):
    def setUp(self):
        self.filter = HealthCheckFilter()

    def _make_record(self, request=None):
        """Create a log record, optionally attaching a request object."""
        record = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Internal Server Error: /health/",
            args=(),
            exc_info=None,
        )
        if request is not None:
            record.request = request
        return record

    def _make_request(self, path):
        """Create a minimal request-like object with a path attribute."""

        class FakeRequest:
            pass

        req = FakeRequest()
        req.path = path
        return req

    def test_suppresses_health_check_request(self):
        """Log records from /health/ requests should be suppressed."""
        record = self._make_record(
            request=self._make_request("/health/")
        )
        self.assertFalse(self.filter.filter(record))

    def test_allows_non_health_check_request(self):
        """Log records from other endpoints should pass through."""
        record = self._make_record(
            request=self._make_request("/profile/")
        )
        self.assertTrue(self.filter.filter(record))

    def test_allows_record_without_request(self):
        """Log records with no request attribute should pass through."""
        record = self._make_record()
        self.assertTrue(self.filter.filter(record))

    def test_suppresses_health_check_without_trailing_slash(self):
        """Should also suppress /health without trailing slash."""
        record = self._make_record(
            request=self._make_request("/health")
        )
        self.assertFalse(self.filter.filter(record))

    def test_allows_path_containing_health_but_not_matching(self):
        """Paths like /api/health-info/ should not be suppressed."""
        record = self._make_record(
            request=self._make_request("/api/health-info/")
        )
        self.assertTrue(self.filter.filter(record))


if __name__ == "__main__":
    unittest.main()
