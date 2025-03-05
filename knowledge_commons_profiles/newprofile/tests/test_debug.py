"""
Test suite for the QueryTimingPanel class

"""

# pylint: disable=broad-exception-caught, import-error
from unittest import TestCase
from unittest.mock import patch

from debug_toolbar.panels import Panel
from django.test import override_settings
from newprofile.debug import QueryTimingPanel


class QueryTimingPanelTestCase(TestCase):
    """Test suite for QueryTimingPanel class"""

    def setUp(self):
        """Set up test environment"""
        self.panel = QueryTimingPanel(toolbar=None, get_response=None)

    def test_panel_inherits_from_base_panel(self):
        """Test that QueryTimingPanel inherits from Panel base class"""
        self.assertIsInstance(self.panel, Panel)

    def test_panel_title(self):
        """Test that panel title is set correctly"""
        self.assertEqual(self.panel.title, "SQL Count")

    @patch("newprofile.debug.connection")
    def test_nav_subtitle_with_no_queries(self, mock_connection):
        """Test nav_subtitle when there are no queries"""
        mock_connection.queries = []
        self.assertEqual(self.panel.nav_subtitle, "0 queries")

    @patch("newprofile.debug.connection")
    def test_nav_subtitle_with_one_query(self, mock_connection):
        """Test nav_subtitle when there is one query"""
        mock_connection.queries = [{"sql": "SELECT 1", "time": "0.001"}]
        self.assertEqual(self.panel.nav_subtitle, "1 queries")

    @patch("newprofile.debug.connection")
    def test_nav_subtitle_with_multiple_queries(self, mock_connection):
        """Test nav_subtitle when there are multiple queries"""
        mock_connection.queries = [
            {"sql": "SELECT 1", "time": "0.001"},
            {"sql": "SELECT 2", "time": "0.002"},
            {"sql": "SELECT 3", "time": "0.003"},
        ]
        self.assertEqual(self.panel.nav_subtitle, "3 queries")

    def test_enable_instrumentation(self):
        """Test enable_instrumentation doesn't raise exceptions"""
        try:
            self.panel.enable_instrumentation()
        except Exception as e:  # noqa: BLE001
            self.fail(
                f"enable_instrumentation raised {type(e).__name__} "
                f"unexpectedly!",
            )

    def test_disable_instrumentation(self):
        """Test disable_instrumentation doesn't raise exceptions"""
        try:
            self.panel.disable_instrumentation()
        except Exception as e:  # noqa: BLE001
            self.fail(
                f"disable_instrumentation raised {type(e).__name__} "
                f"unexpectedly!",
            )

    @override_settings(DEBUG=False)
    def test_panel_with_debug_disabled(self):
        """Test panel functions correctly when DEBUG is False"""
        with patch("newprofile.debug.connection") as mock_connection:
            mock_connection.queries = [{"sql": "SELECT 1", "time": "0.001"}]
            self.assertEqual(self.panel.nav_subtitle, "1 queries")

    @patch("newprofile.debug.connection")
    def test_nav_subtitle_with_updated_connection(self, mock_connection):
        """Test nav_subtitle updates when connection.queries changes"""
        # Start with one query
        mock_connection.queries = [{"sql": "SELECT 1", "time": "0.001"}]
        self.assertEqual(self.panel.nav_subtitle, "1 queries")

        # Update to three queries
        mock_connection.queries = [
            {"sql": "SELECT 1", "time": "0.001"},
            {"sql": "SELECT 2", "time": "0.002"},
            {"sql": "SELECT 3", "time": "0.003"},
        ]
        self.assertEqual(self.panel.nav_subtitle, "3 queries")
