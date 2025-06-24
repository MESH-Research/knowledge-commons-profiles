"""
Tests for utility functions in the knowledge_commons_profiles app
"""

import json
from unittest.mock import MagicMock
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.test.utils import override_settings

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    ProfileFactory,
)
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    WpUserFactory,
)
from knowledge_commons_profiles.newprofile.utils import process_orders
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)

# ruff: noqa: PLC0415


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


class TestProcessOrders(TestCase):
    """Test cases for the process_orders function"""

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me", "interests"],
        PROFILE_FIELDS_RIGHT=["email", "website", "social_media"],
    )
    def test_basic_processing(self):
        """Test basic processing of orders with standard input"""
        left_order = ["name-form", "about_me-form"]
        right_order = ["email-form", "website-form"]

        left_result, right_result = process_orders(left_order, right_order)

        # Check left order results
        self.assertEqual(left_result, ["name", "about_me", "interests"])

        # Check right order results
        self.assertEqual(right_result, ["email", "website", "social_media"])

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me", "interests", "education"],
        PROFILE_FIELDS_RIGHT=["email", "website", "social_media", "phone"],
    )
    def test_reordering(self):
        """Test that the order in the input is preserved"""
        # Intentionally order differently than the settings
        left_order = ["interests-form", "name-form", "education-form"]
        right_order = ["phone-form", "email-form"]

        left_result, right_result = process_orders(left_order, right_order)

        # Check that order is preserved for items in the input
        self.assertEqual(left_result[0], "interests")
        self.assertEqual(left_result[1], "name")
        self.assertEqual(left_result[2], "education")

        # The item not in the input should be appended
        self.assertEqual(left_result[3], "about_me")

        # Similar check for right order
        self.assertEqual(right_result[0], "phone")
        self.assertEqual(right_result[1], "email")

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me"],
        PROFILE_FIELDS_RIGHT=["email", "website"],
    )
    def test_items_not_in_allowed_list(self):
        """Test items that aren't in the allowed lists are excluded"""
        left_order = ["name-form", "invalid_field-form"]
        right_order = ["invalid_field-form", "email-form"]

        left_result, right_result = process_orders(left_order, right_order)

        # Check that invalid items are excluded
        self.assertEqual(left_result, ["name", "about_me"])
        self.assertEqual(right_result, ["email", "website"])

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me"],
        PROFILE_FIELDS_RIGHT=["email", "website"],
    )
    def test_different_formats(self):
        """Test handling of different input formats (form, edit, dashes,
        underscores)"""
        left_order = ["name-form", "about-me_edit"]
        right_order = ["email_edit", "website-edit"]

        left_result, right_result = process_orders(left_order, right_order)

        # Check normalization of different formats
        self.assertEqual(left_result, ["name", "about_me"])
        self.assertEqual(right_result, ["email", "website"])

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me", "interests"],
        PROFILE_FIELDS_RIGHT=["email", "website", "social_media"],
    )
    def test_empty_input(self):
        """Test with empty inputs"""
        left_order = []
        right_order = []

        left_result, right_result = process_orders(left_order, right_order)

        # All allowed fields should be included in the default order
        self.assertEqual(left_result, ["name", "about_me", "interests"])
        self.assertEqual(right_result, ["email", "website", "social_media"])

    @override_settings(
        PROFILE_FIELDS_LEFT=["name", "about_me"],
        PROFILE_FIELDS_RIGHT=["email", "website"],
    )
    def test_duplicate_entries(self):
        """Test that duplicate entries in input are handled correctly"""
        left_order = ["name-form", "name-form", "about_me-form"]
        right_order = ["email-form", "email-form"]

        left_result, right_result = process_orders(left_order, right_order)

        self.assertEqual(left_result, ["name", "name", "about_me"])
        self.assertEqual(right_result, ["email", "email", "website"])

    @override_settings(PROFILE_FIELDS_LEFT=[], PROFILE_FIELDS_RIGHT=[])
    def test_empty_settings(self):
        """Test with empty settings"""
        left_order = ["name-form", "about_me-form"]
        right_order = ["email-form", "website-form"]

        left_result, right_result = process_orders(left_order, right_order)

        # Nothing should be in the result with empty allowed lists
        self.assertEqual(left_result, [])
        self.assertEqual(right_result, [])


class HideWorkTests(TestCase):

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_hide_nothing(self, mock_hidden_works):
        """
        Test hiding nothing
        """
        mock_hidden_works.HIDE = "HIDE"
        work = MagicMock()
        work.id = "123"
        hidden_works = "SHOW"  # Not HIDE
        visibility = {"show_works_article": True}
        visibility_works = {"show_works_work_123": True}

        from knowledge_commons_profiles.newprofile.utils import hide_work

        result = hide_work(
            work, "article", hidden_works, visibility, visibility_works
        )

        self.assertEqual(result, (False, False))

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_hide_heading_only(self, mock_hidden_works):
        """
        Test hiding a heading
        """
        mock_hidden_works.HIDE = "HIDE"
        work = MagicMock()
        work.id = "456"
        hidden_works = "HIDE"
        visibility = {"show_works_book": False}
        visibility_works = {"show_works_work_456": True}

        from knowledge_commons_profiles.newprofile.utils import hide_work

        result = hide_work(
            work, "book", hidden_works, visibility, visibility_works
        )

        self.assertEqual(result, (True, False))

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_hide_individual_work_only(self, mock_hidden_works):
        """
        Test hiding an individual work
        """
        mock_hidden_works.HIDE = "HIDE"
        work = MagicMock()
        work.id = "789"
        hidden_works = "HIDE"
        visibility = {"show_works_paper": True}
        visibility_works = {"show_works_work_789": False}

        from knowledge_commons_profiles.newprofile.utils import hide_work

        result = hide_work(
            work, "paper", hidden_works, visibility, visibility_works
        )

        self.assertEqual(result, (False, True))

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_hide_both_heading_and_work(self, mock_hidden_works):
        """
        Test hiding both
        """
        mock_hidden_works.HIDE = "HIDE"
        work = MagicMock()
        work.id = "999"
        hidden_works = "HIDE"
        visibility = {"show_works_report": False}
        visibility_works = {"show_works_work_999": False}

        from knowledge_commons_profiles.newprofile.utils import hide_work

        result = hide_work(
            work, "report", hidden_works, visibility, visibility_works
        )

        self.assertEqual(result, (True, True))


class GetVisibilitiesTests(TestCase):

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_no_user_profile(self, mock_hidden_works):
        """
        Test with no user profile
        """
        mock_hidden_works.HIDE = "HIDE"

        instance = MagicMock()
        instance.user_profile = None

        from knowledge_commons_profiles.newprofile.utils import get_visibilities

        visibility, visibility_works = get_visibilities(
            instance, mock_hidden_works.HIDE
        )
        self.assertEqual(visibility, {})
        self.assertEqual(visibility_works, {})

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_user_profile_with_no_fields(self, mock_hidden_works):
        """
        Test with no fields
        """
        mock_hidden_works.HIDE = "HIDE"

        user_profile = MagicMock()
        user_profile.works_show = None
        user_profile.works_work_show = None

        instance = MagicMock()
        instance.user_profile = user_profile

        from knowledge_commons_profiles.newprofile.utils import get_visibilities

        visibility, visibility_works = get_visibilities(
            instance, mock_hidden_works.HIDE
        )
        self.assertEqual(visibility, {})
        self.assertEqual(visibility_works, {})

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_user_profile_with_valid_fields(self, mock_hidden_works):
        """
        Test with valid fields
        """
        mock_hidden_works.HIDE = "HIDE"

        visibility_data = {"show_works_article": True}
        visibility_works_data = {"show_works_work_123": False}

        user_profile = MagicMock()
        user_profile.works_show = json.dumps(visibility_data)
        user_profile.works_work_show = json.dumps(visibility_works_data)

        instance = MagicMock()
        instance.user_profile = user_profile

        from knowledge_commons_profiles.newprofile.utils import get_visibilities

        visibility, visibility_works = get_visibilities(
            instance, mock_hidden_works.HIDE
        )
        self.assertEqual(visibility, visibility_data)
        self.assertEqual(visibility_works, visibility_works_data)

    @patch("knowledge_commons_profiles.newprofile.works.HiddenWorks")
    def test_hidden_works_not_hide(self, mock_hidden_works):
        """
        Test with hidden works not HIDE
        """
        mock_hidden_works.HIDE = "HIDE"

        user_profile = MagicMock()
        user_profile.works_show = json.dumps({"some_key": False})
        user_profile.works_work_show = json.dumps({"some_work": True})

        instance = MagicMock()
        instance.user_profile = user_profile

        from knowledge_commons_profiles.newprofile.utils import get_visibilities

        visibility, visibility_works = get_visibilities(instance, "SHOW")
        self.assertEqual(visibility, {})
        self.assertEqual(visibility_works, {})
