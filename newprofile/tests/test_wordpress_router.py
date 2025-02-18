"""
Test suite for the ReadWriteRouter class
"""

from unittest import mock

import pytest

# pylint: disable=import-error, too-few-public-methods
from newprofile.wordpress_router import (
    ReadWriteRouter,
)


class TestReadWriteRouter:
    """Test suite for the ReadWriteRouter class."""

    @pytest.fixture
    def router(self):
        """Return a ReadWriteRouter instance for testing."""
        return ReadWriteRouter()

    def test_db_for_read_with_wp_model(self, router):
        """Test that WordPress models are routed to wordpress_dev for reads."""

        class WpPost:
            """
            This is a post
            """

        result = router.db_for_read(WpPost)
        assert result == router.db_name

    def test_db_for_read_with_non_wp_model(self, router):
        """Test that non-WordPress models are routed to default for reads."""

        class User:
            """
            This is a user
            """

        result = router.db_for_read(User)
        assert result == "default"

    def test_db_for_read_with_uppercase_wp_model(self, router):
        """Test that WP models with uppercase names are correctly identified."""

        class WPCategory:
            """
            This is a category
            """

        result = router.db_for_read(WPCategory)
        assert result == router.db_name

    def test_db_for_write_with_wp_model(self, router):
        """Test that writes to WordPress models return None (disallowed)."""

        class WpComment:
            """
            This is a comment
            """

        result = router.db_for_write(WpComment)
        assert result is None

    def test_db_for_write_with_non_wp_model(self, router):
        """Test that non-WordPress models are routed to default for writes."""

        class Product:
            """
            This is a product
            """

        result = router.db_for_write(Product)
        assert result == "default"

    def test_db_for_write_with_mixed_case_wp_model(self, router):
        """Test that WP models with mixed case are correctly identified."""

        class WpUser:
            """
            This is a user
            """

        result = router.db_for_write(WpUser)
        assert result is None

    def test_allow_migrate_default_db(self, router):
        """Test that migrations are allowed on the default database."""
        result = router.allow_migrate("default", "auth")
        assert result is True

    def test_allow_migrate_wordpress_db(self, router):
        """Test that migrations are not allowed on the wordpress database."""
        result = router.allow_migrate(router.db_name, "wordpress")
        assert result is False

    def test_allow_migrate_with_model_name(self, router):
        """Test migration control with explicit model_name parameter."""
        result = router.allow_migrate(
            "default", "wordpress", model_name="wppost"
        )
        assert result is True

    def test_allow_migrate_ignores_app_and_model(self, router):
        """Test that allow_migrate only considers the database name."""
        # Even for WordPress models, migrations should be allowed on default DB
        result = router.allow_migrate(
            "default", "wordpress", model_name="wppost"
        )
        assert result is True

    def test_db_for_read_with_hints(self, router):
        """Test db_for_read works correctly when hints are provided."""

        class WpTerm:
            """
            This is a term
            """

        result = router.db_for_read(WpTerm, instance=mock.Mock())
        assert result == router.db_name

    def test_db_for_write_with_hints(self, router):
        """Test db_for_write works correctly when hints are provided."""

        class WpOption:
            """
            This is an option
            """

        result = router.db_for_write(WpOption, using="some_hint")
        assert result is None

    def test_edge_case_model_name_with_wp_substring(self, router):
        """Test models with 'wp' not at the start are routed correctly."""

        class MyWpModel:  # Doesn't start with 'wp'
            """
            This is a model
            """

        read_result = router.db_for_read(MyWpModel)
        write_result = router.db_for_write(MyWpModel)

        assert read_result == "default"
        assert write_result == "default"
