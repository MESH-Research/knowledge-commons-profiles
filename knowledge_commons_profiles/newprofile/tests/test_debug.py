"""
Test suite for the QueryTimingPanel class

"""

# pylint: disable=broad-exception-caught, import-error
from unittest import TestCase
from unittest.mock import patch

from debug_toolbar.panels import Panel

from knowledge_commons_profiles.newprofile.debug import QueryTimingPanel


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
