"""
Test suite for the ReadWriteRouter class
"""

from unittest import mock

# pylint: disable=too-few-public-methods, import-error
from django.test import TestCase

from knowledge_commons_profiles.newprofile.wordpress_router import (
    ReadWriteRouter,
)


class ReadWriteRouterTests(TestCase):
    """Test suite for the ReadWriteRouter class."""

    def setUp(self):
        """Set up a ReadWriteRouter instance for testing."""
        self.router = ReadWriteRouter()

    def test_db_for_read_with_wp_model(self):
        """Test that WordPress models are routed to wordpress DB for reads."""

        class WpPost:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_read(WpPost)
        self.assertEqual(result, self.router.db_name)

    def test_db_for_read_with_non_wp_model(self):
        """Test that non-WordPress models are routed to default for reads."""

        class User:
            """
            A model that doesn't start with 'wp'
            """

        result = self.router.db_for_read(User)
        self.assertEqual(result, "default")

    def test_db_for_read_with_uppercase_wp_model(self):
        """Test that WP models with uppercase names are correctly identified."""

        class WPCategory:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_read(WPCategory)
        self.assertEqual(result, self.router.db_name)

    def test_db_for_write_with_wp_model(self):
        """Test that writes to WordPress models return None (disallowed)."""

        class WpComment:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_write(WpComment)
        self.assertIsNone(result)

    def test_db_for_write_with_non_wp_model(self):
        """Test that non-WordPress models are routed to default for writes."""

        class Product:
            """
            A model that doesn't start with 'wp'
            """

        result = self.router.db_for_write(Product)
        self.assertEqual(result, "default")

    def test_db_for_write_with_mixed_case_wp_model(self):
        """Test that WP models with mixed case are correctly identified."""

        class WpUser:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_write(WpUser)
        self.assertIsNone(result)

    def test_allow_migrate_default_db(self):
        """Test that migrations are allowed on the default database."""
        result = self.router.allow_migrate("default", "auth")
        self.assertTrue(result)

    def test_allow_migrate_wordpress_db(self):
        """Test that migrations are not allowed on the wordpress database."""
        result = self.router.allow_migrate(self.router.db_name, "wordpress")
        self.assertFalse(result)

    def test_allow_migrate_with_model_name(self):
        """Test migration control with explicit model_name parameter."""
        result = self.router.allow_migrate(
            "default",
            "wordpress",
            model_name="wppost",
        )
        self.assertTrue(result)

    def test_allow_migrate_ignores_app_and_model(self):
        """Test that allow_migrate only considers the database name."""
        # Even for WordPress models, migrations should be allowed on default DB
        result = self.router.allow_migrate(
            "default",
            "wordpress",
            model_name="wppost",
        )
        self.assertTrue(result)

    def test_db_for_read_with_hints(self):
        """Test db_for_read works correctly when hints are provided."""

        class WpTerm:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_read(WpTerm, instance=mock.Mock())
        self.assertEqual(result, self.router.db_name)

    def test_db_for_write_with_hints(self):
        """Test db_for_write works correctly when hints are provided."""

        class WpOption:
            """
            A model that starts with 'wp'
            """

        result = self.router.db_for_write(WpOption, using="some_hint")
        self.assertIsNone(result)

    def test_edge_case_model_name_with_wp_substring(self):
        """Test models with 'wp' not at the start are routed correctly."""

        class MyWpModel:  # Doesn't start with 'wp'
            """
            A model that doesn't start with 'wp'
            """

        read_result = self.router.db_for_read(MyWpModel)
        write_result = self.router.db_for_write(MyWpModel)

        self.assertEqual(read_result, "default")
        self.assertEqual(write_result, "default")
