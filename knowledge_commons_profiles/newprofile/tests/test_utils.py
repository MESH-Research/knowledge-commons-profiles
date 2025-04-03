"""
Tests for utility functions in the knowledge_commons_profiles app
"""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    ProfileFactory,
)
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    WpUserFactory,
)
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)


class TestProfileExistsOrHasBeenCreated(TestCase):
    """Test the profile_exists_or_has_been_created function"""

    def setUp(self):
        """Set up test data"""
        # Clear any existing data to ensure clean test environment
        Profile.objects.all().delete()
        # We don't delete WpUser objects as they might be managed
        # separately (and we only have RO DB access)

    @patch("knowledge_commons_profiles.newprofile.utils.logger")
    def test_profile_already_exists(self, mock_logger):
        """Test when the profile already exists"""
        # Create a profile
        test_username = "existing_user"
        _ = ProfileFactory(username=test_username)

        # Call the function
        result = profile_exists_or_has_been_created(test_username)

        # Assertions
        self.assertTrue(result)
        # Verify logger wasn't called
        mock_logger.warning.assert_not_called()

    @patch(
        "knowledge_commons_profiles.newprofile.utils.Profile.objects.create"
    )
    @patch("knowledge_commons_profiles.newprofile.utils.logger")
    @patch("knowledge_commons_profiles.newprofile.utils.WpUser.objects")
    def test_profile_created_from_wp_user(
        self, mock_wp_user_objects, mock_logger, mock_create
    ):
        """Test when the profile is created from an existing WordPress user"""
        # Set up test data
        test_username = "wp_user_without_profile"

        # Create a WP user but no profile
        wpuser = WpUserFactory(user_login=test_username)

        # Configure the mock
        mock_filter = MagicMock()
        mock_filter.first.return_value = wpuser
        mock_wp_user_objects.filter.return_value = mock_filter

        # Call the function
        result = profile_exists_or_has_been_created(test_username)

        # Assertions
        self.assertTrue(result)
        mock_create.assert_called_once_with(username=test_username)
        mock_logger.warning.assert_not_called()

    @patch(
        "knowledge_commons_profiles.newprofile.utils.Profile.objects.filter"
    )
    @patch("knowledge_commons_profiles.newprofile.utils.WpUser.objects.filter")
    @patch("knowledge_commons_profiles.newprofile.utils.logger")
    def test_no_profile_no_wp_user(
        self, mock_logger, mock_wp_filter, mock_profile_filter
    ):
        """Test when neither profile nor WordPress user exists"""
        # Set up mocks
        mock_profile_filter.return_value.first.return_value = None
        mock_wp_filter.return_value.first.return_value = None

        # Call the function
        result = profile_exists_or_has_been_created("nonexistent_user")

        # Assertions
        self.assertFalse(result)
        mock_logger.warning.assert_not_called()

    @patch("knowledge_commons_profiles.newprofile.utils.Profile.objects")
    @patch("knowledge_commons_profiles.newprofile.utils.WpUser.objects")
    @patch("knowledge_commons_profiles.newprofile.utils.logger")
    def test_operational_error_on_profile_creation(
        self,
        mock_logger,
        mock_wp_filter,
        mock_profile_objects,
    ):
        """Test when there's an operational error during profile creation"""
        # Set up test data
        test_username = "user_with_creation_error"

        # Configure mocks
        # mock Profiles
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_profile_objects.filter.return_value = mock_filter

        # Set up the error to be raised during creation
        mock_profile_objects.create = MagicMock()
        mock_profile_objects.create.side_effect = OperationalError(
            "Could not connect to database"
        )

        # mock WpUser
        mock_wp_user = MagicMock()
        mock_wp_user.user_login = test_username
        mock_filter_wp = MagicMock()
        mock_filter_wp.first.return_value = mock_wp_user
        mock_wp_filter.filter.return_value = mock_filter_wp

        # Call the function
        self.assertFalse(profile_exists_or_has_been_created(test_username))

        # Assertion to check the error was logged
        mock_logger.warning.assert_called_once_with(
            "Unable to connect to MySQL database to create Profile"
        )

    @patch("knowledge_commons_profiles.newprofile.utils.WpUser.objects.filter")
    @patch(
        "knowledge_commons_profiles.newprofile.utils.Profile.objects.filter"
    )
    @patch("knowledge_commons_profiles.newprofile.utils.logger")
    def test_operational_error_on_wp_user_check(
        self, mock_logger, mock_profile_filter, mock_wp_filter
    ):
        """Test when there's an operational error during WordPress user
        check"""
        # Set up mocks
        mock_profile_filter.return_value.first.return_value = None
        mock_wp_filter.side_effect = OperationalError(
            "Could not connect to WordPress database"
        )

        # Call the function
        result = profile_exists_or_has_been_created("user_with_db_error")

        # Assertions
        self.assertFalse(result)
        # Verify logger wasn't called as this error is expected
        mock_logger.warning.assert_not_called()
