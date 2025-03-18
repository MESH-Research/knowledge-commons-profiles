"""Tests for version detection module.

This module tests the version detection logic in the __init__.py
file, ensuring it correctly handles both the presence and absence
of a pyproject.toml file.
"""

import sys
import unittest
from unittest import mock


class TestVersionDetection(unittest.TestCase):
    """Test cases for version detection from pyproject.toml."""

    @mock.patch("knowledge_commons_profiles.newprofile.Path.exists")
    def test_pyproject_toml_not_found(self, mock_exists):
        """Test handling when pyproject.toml cannot be found."""
        # Arrange
        mock_exists.return_value = False  # Pretend the file exists

        sys.modules.pop("knowledge_commons_profiles.newprofile")

        import knowledge_commons_profiles.newprofile

        self.assertTrue(
            knowledge_commons_profiles.newprofile.__version__
            == "Unknown build"
        )

        # Verify mock was called as expected
        mock_exists.assert_called_once()
