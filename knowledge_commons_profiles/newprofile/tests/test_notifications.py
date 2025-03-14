from unittest import mock

from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.newprofile.notifications import (
    BuddyPressNotification,
)


class BuddyPressNotificationTests(TestCase):
    """Tests for the BuddyPressNotification class."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create a mock notification item
        self.notification_item = mock.MagicMock()
        self.notification_item.component_action = "test_action"
        self.notification_item.item_id = 42
        self.notification_item.secondary_item_id = 99
        self.notification_item.user_id = 123
        self.notification_item.component_name = "test_component"
        self.notification_item.is_new = True

        # Create the notification instance
        self.notification = BuddyPressNotification(self.notification_item)

        # Mock API class
        self.api_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.API"
        )
        self.mock_api_class = self.api_patcher.start()

        # Create a mock API instance
        self.mock_api = mock.MagicMock()
        self.mock_api.wp_user = mock.MagicMock()
        self.mock_api.wp_user.user_login = "testuser"

        # Configure API class to return our mock instance
        self.mock_api_class.return_value = self.mock_api

        # Mock WpBpGroup.objects.get
        self.group_get_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.notifications."
            "WpBpGroup.objects.get"
        )
        self.mock_group_get = self.group_get_patcher.start()

        # Mock WpUser.objects.get
        self.user_get_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.notifications."
            "WpUser.objects.get"
        )
        self.mock_user_get = self.user_get_patcher.start()

        # Mock WpBpNotification.objects.filter
        self.notification_filter_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.notifications."
            "WpBpNotification.objects.filter"
        )
        self.mock_notification_filter = (
            self.notification_filter_patcher.start()
        )

        # Set up filter chain
        self.mock_filter_result = mock.MagicMock()
        self.mock_notification_filter.return_value = self.mock_filter_result

    def tearDown(self):
        """Clean up after the tests."""
        self.api_patcher.stop()
        self.group_get_patcher.stop()
        self.user_get_patcher.stop()
        self.notification_filter_patcher.stop()

    def test_str_method(self):
        """Test the __str__ method."""
        # Mock get_string to return a value
        with mock.patch.object(
            self.notification, "get_string", return_value=["Test notification"]
        ):
            # Call __str__
            result = str(self.notification)

            # Assert result is as expected
            self.assertEqual(result, "Test notification")

    def test_str_method_empty_result(self):
        """Test the __str__ method when get_string returns empty."""
        # Mock get_string to return None
        with mock.patch.object(
            self.notification, "get_string", return_value=None
        ):
            # Call __str__
            result = str(self.notification)

            # Assert result is an empty string
            self.assertEqual(result, "")

    def test_get_string_group_invite(self):
        """Test get_string for group_invite notification."""
        # Set up notification type
        self.notification_item.component_action = "group_invite"

        # Set up mock group
        mock_group = mock.MagicMock()
        mock_group.name = "Test Group"
        self.mock_group_get.return_value = mock_group

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert API was instantiated correctly
        self.mock_api_class.assert_called_once_with(
            self.notification.request,
            "testuser",
            use_wordpress=True,
            create=False,
        )

        # Assert group was fetched
        self.mock_group_get.assert_called_once_with(id=42)

        # Assert result is as expected
        expected_message = "You have an invitation to the group: Test Group"
        expected_url = (
            "https://hcommons.org/members/testuser/groups/invites/?n=1"
        )
        expected_is_django_url = False

        self.assertEqual(
            result, (expected_message, expected_url, expected_is_django_url)
        )

    def test_get_string_group_invite_not_found(self):
        """Test get_string for group_invite when group doesn't exist."""
        # Set up notification type
        self.notification_item.component_action = "group_invite"

        # Set up mock group.get to raise DoesNotExist
        self.mock_group_get.side_effect = WpBpGroup.DoesNotExist

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert group was attempted to be fetched
        self.mock_group_get.assert_called_once_with(id=42)

        # Assert result is empty
        self.assertEqual(result, ("", None, False))

    def test_get_string_new_message(self):
        """Test get_string for new_message notification."""
        # Set up notification type
        self.notification_item.component_action = "new_message"

        # Set up mock user
        mock_user = mock.MagicMock()
        mock_user.user_login = "sender_user"
        self.mock_user_get.return_value = mock_user

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert user was fetched
        self.mock_user_get.assert_called_once_with(id=99)

        # Assert result is as expected
        expected_message = "New message from sender_user"
        expected_url = (
            "https://hcommons.org/members/testuser/messages/view/42/"
        )
        expected_is_django_url = False

        self.assertEqual(
            result, (expected_message, expected_url, expected_is_django_url)
        )

    def test_get_string_new_follow_short(self):
        """Test get_string for new_follow notification with short=True."""
        # Set up notification type
        self.notification_item.component_action = "new_follow"

        # Set up mock filter to return count
        self.mock_filter_result.count.return_value = 5

        # Call method with short=True
        result = self.notification.get_string(username="testuser", short=True)

        # Assert filter was called with correct parameters
        self.mock_notification_filter.assert_called_once_with(
            user_id=123,
            component_name="test_component",
            component_action="new_follow",
            is_new=True,
        )

        # Assert result is as expected
        expected_message = "You have 5 new followers"
        expected_url = "https://hcommons.org/members/testuser/notifications/"
        expected_is_django_url = False

        self.assertEqual(
            result, (expected_message, expected_url, expected_is_django_url)
        )

    def test_get_string_new_follow_normal(self):
        """Test get_string for new_follow notification with short=False."""
        # Set up notification type
        self.notification_item.component_action = "new_follow"

        # Set up mock user
        mock_user = mock.MagicMock()
        mock_user.user_login = "follower_user"
        mock_user.display_name = "Follower User"
        self.mock_user_get.return_value = mock_user

        # Call method with short=False (default)
        result = self.notification.get_string(username="testuser")

        # Assert user was fetched
        self.mock_user_get.assert_called_once_with(id=42)

        # Assert result is as expected
        expected_message = "Follower User is now following you"
        expected_url = ("profile", "follower_user")
        expected_is_django_url = True

        self.assertEqual(
            result, (expected_message, expected_url, expected_is_django_url)
        )

    def test_get_string_new_user_email_settings(self):
        """Test get_string for new_user_email_settings notification."""
        # Set up notification type
        self.notification_item.component_action = "new_user_email_settings"

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert result is as expected
        expected_message = "Welcome! Be sure to review your email preferences."
        expected_url = None
        expected_is_django_url = False

        self.assertEqual(
            result, (expected_message, expected_url, expected_is_django_url)
        )

    def test_get_string_unknown_action(self):
        """Test get_string for unknown notification type."""
        # Set up notification type
        self.notification_item.component_action = "unknown_action"

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert result is empty string
        self.assertEqual(result, "")

    def test_get_string_no_api(self):
        """Test get_string when API returns None."""
        # Configure API class to return None
        self.mock_api_class.return_value = None

        # Call method
        result = self.notification.get_string(username="testuser")

        # Assert API was instantiated
        self.mock_api_class.assert_called_once()

        # Assert result is the error message
        self.assertEqual(result, "User not logged in")

    def test_get_string_with_request(self):
        """Test get_string when request is provided."""
        # Create a notification with request
        mock_request = mock.MagicMock()
        notification_with_request = BuddyPressNotification(
            self.notification_item, request=mock_request
        )

        # Set up notification type
        self.notification_item.component_action = "new_user_email_settings"

        # Call method
        result = notification_with_request.get_string(username="testuser")

        # Assert API was instantiated with request
        self.mock_api_class.assert_called_once_with(
            mock_request,
            "testuser",
            use_wordpress=True,
            create=False,
        )

        # Assert result is as expected
        expected_message = "Welcome! Be sure to review your email preferences."
        self.assertEqual(result[0], expected_message)
