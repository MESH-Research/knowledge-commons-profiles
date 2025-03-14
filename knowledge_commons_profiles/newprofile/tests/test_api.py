import asyncio
import hashlib
from unittest import mock
from urllib.parse import urlencode

import django.test
from django.core.exceptions import ObjectDoesNotExist
from django.test.client import RequestFactory

import knowledge_commons_profiles.newprofile.api
from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    ProfileFactory,
)
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    UserFactory,
)


def set_up_api_instance():
    """
    Fixture to create a model instance with a profile
    :return:
    """
    rf = RequestFactory()
    get_request = rf.get("/user/kfitz")
    user = UserFactory(
        username="testuser",
        email="test@example.com",
        password="testpass",
    )
    # Create the model instance
    return (
        knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=user
        ),
        user,
    )


class TestWorksHtmlPropertyTests(django.test.TransactionTestCase):
    """Tests for the works_html cached async property."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create a test user
        self.model_instance, self.user = set_up_api_instance()

        # Initialize instance variables to None as they would be in the
        # real class
        self.model_instance._works_deposits = None
        self.model_instance._works_html = None

        # Create a mock for WorksDeposits
        self.works_deposits_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WorksDeposits"
        )
        self.mock_works_deposits = self.works_deposits_patcher.start()

        # Create a mock instance for the WorksDeposits class
        self.mock_works_deposits_instance = mock.MagicMock()
        self.mock_works_deposits.return_value = (
            self.mock_works_deposits_instance
        )

        # Set up the display_filter mock to return a coroutine
        self.mock_html_content = "<div>Sample Works HTML</div>"
        self.mock_works_deposits_instance.display_filter.return_value = (
            asyncio.Future()
        )
        self.mock_works_deposits_instance.display_filter.return_value.set_result(
            self.mock_html_content
        )

    def tearDown(self):
        """Clean up after the tests."""
        self.works_deposits_patcher.stop()

    async def test_works_html_with_existing_deposits(self):
        """Test that works_html uses existing _works_deposits if available."""
        # Set up an existing _works_deposits
        mock_existing_deposits = mock.MagicMock()
        mock_existing_deposits.display_filter.return_value = asyncio.Future()
        mock_existing_deposits.display_filter.return_value.set_result(
            "<div>Existing Deposits</div>"
        )

        self.model_instance._works_deposits = mock_existing_deposits

        # Call the property
        result = await self.model_instance.works_html

        # Assert WorksDeposits was not initialized again
        self.mock_works_deposits.assert_not_called()

        # Assert the existing instance's display_filter was called
        mock_existing_deposits.display_filter.assert_called_once()

        # Assert the result is as expected
        self.assertEqual(result, "<div>Existing Deposits</div>")

    async def test_works_html_with_existing_html(self):
        """Test that works_html returns cached _works_html if available."""
        # Set up existing _works_html
        existing_html = "<div>Pre-cached HTML</div>"
        self.model_instance._works_html = existing_html

        # Call the property
        result = await self.model_instance.works_html

        # Assert display_filter was not called
        self.mock_works_deposits_instance.display_filter.assert_not_called()

        # Assert the result is the cached HTML
        self.assertEqual(result, existing_html)

    @mock.patch(
        "knowledge_commons_profiles.newprofile.api.WorksDeposits",
        side_effect=Exception("WorksDeposits initialization error"),
    )
    async def test_works_deposits_initialization_error(self, mock_init):
        """Test handling of errors during WorksDeposits initialization."""
        # Reset _works_deposits to None
        self.model_instance._works_deposits = None

        # Call the property and expect an exception
        with self.assertRaises(Exception) as context:
            await self.model_instance.works_html

        # Assert the error message is as expected
        self.assertEqual(
            str(context.exception), "WorksDeposits initialization error"
        )


class WorksHtmlIntegrationTests(django.test.TransactionTestCase):
    """Integration tests for the works_html property with actual
    dependencies."""

    @mock.patch("knowledge_commons_profiles.newprofile.api.WorksDeposits")
    async def test_end_to_end_works_html_flow(self, mock_works_deposits):
        """Test the complete flow of works_html with mocked external
        dependencies."""
        # Set up the mock
        mock_instance = mock.MagicMock()
        mock_works_deposits.return_value = mock_instance
        mock_instance.display_filter.return_value = asyncio.Future()
        mock_instance.display_filter.return_value.set_result(
            "<div>Integration Test HTML</div>"
        )

        # Create a real user
        model_instance, user = set_up_api_instance()

        # Call the property
        result = await model_instance.works_html

        # Assert the expected interactions and results
        mock_works_deposits.assert_called_once_with(
            user, "https://works.hcommons.org"
        )
        mock_instance.display_filter.assert_called_once()
        self.assertEqual(result, "<div>Integration Test HTML</div>")


class WorksDepositsPropertyTests(django.test.TransactionTestCase):
    """Tests for the works_deposits cached async property."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create mock profile_info with username
        self.test_username = "test_user"
        self.profile_info = {
            "username": self.test_username,
            "email": "test@example.com",
        }

        self.model_instance, self.user = set_up_api_instance()
        self.model_instance._profile_info = self.profile_info

        # Set _works_deposits to None as it would be in the real class
        self.model_instance._works_deposits = None

        # Create a mock for WorksDeposits
        self.works_deposits_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WorksDeposits"
        )
        self.mock_works_deposits_class = self.works_deposits_patcher.start()

        # Create a mock instance that will be returned by the WorksDeposits
        # constructor
        self.mock_works_deposits_instance = mock.MagicMock()
        self.mock_works_deposits_class.return_value = (
            self.mock_works_deposits_instance
        )

    def tearDown(self):
        """Clean up after the tests."""
        self.works_deposits_patcher.stop()

    async def test_works_deposits_initialization(self):
        """Test that works_deposits initializes WorksDeposits if it's None."""
        # Call the property
        result = await self.model_instance.works_deposits

        # Assert WorksDeposits was initialized with correct parameters
        self.mock_works_deposits_class.assert_called_once_with(
            self.test_username, "https://works.hcommons.org"
        )

        # Assert the result is the mock instance
        self.assertEqual(result, self.mock_works_deposits_instance)

        # Assert that _works_deposits is now set
        self.assertIsNotNone(self.model_instance._works_deposits)
        self.assertEqual(
            self.model_instance._works_deposits,
            self.mock_works_deposits_instance,
        )

    async def test_works_deposits_caching(self):
        """Test that works_deposits caches the instance and doesn't
        reinitialize."""
        # Call the property twice
        result1 = await self.model_instance.works_deposits
        result2 = await self.model_instance.works_deposits

        # Assert WorksDeposits was initialized only once
        self.mock_works_deposits_class.assert_called_once()

        # Assert both results are the same
        self.assertEqual(result1, result2)
        self.assertEqual(result1, self.mock_works_deposits_instance)

    async def test_works_deposits_with_existing_instance(self):
        """Test that works_deposits returns existing _works_deposits if
        available."""
        # Set up an existing _works_deposits
        existing_deposits = mock.MagicMock()
        self.model_instance._works_deposits = existing_deposits

        # Call the property
        result = await self.model_instance.works_deposits

        # Assert WorksDeposits was not initialized again
        self.mock_works_deposits_class.assert_not_called()

        # Assert the result is the existing instance
        self.assertEqual(result, existing_deposits)

    @mock.patch(
        "knowledge_commons_profiles.newprofile.api.WorksDeposits",
        side_effect=Exception("WorksDeposits initialization error"),
    )
    async def test_works_deposits_initialization_error(self, mock_init):
        """Test handling of errors during WorksDeposits initialization."""
        # Reset _works_deposits to None
        self.model_instance._works_deposits = None

        # Call the property and expect an exception
        with self.assertRaises(Exception) as context:
            await self.model_instance.works_deposits

        # Assert the error message is as expected
        self.assertEqual(
            str(context.exception), "WorksDeposits initialization error"
        )


class WorksDepositsPropertyIntegrationTests(django.test.TransactionTestCase):
    """Integration tests for the works_deposits property with actual
    dependencies."""

    def setUp(self):
        """Set up test data for integration tests."""
        self.model_instance, self.user = set_up_api_instance()
        self.model_instance._profile_info = {"username": "integration_user"}
        self.model_instance._works_deposits = None

    @mock.patch("knowledge_commons_profiles.newprofile.api.WorksDeposits")
    async def test_end_to_end_works_deposits_flow(self, mock_works_deposits):
        """Test the complete flow of works_deposits with mocked external
        dependencies."""
        # Set up the mock to return a specific object
        mock_instance = mock.MagicMock()
        mock_instance.name = "Mocked WorksDeposits Instance"
        mock_works_deposits.return_value = mock_instance

        # Call the property
        result = await self.model_instance.works_deposits

        # Assert the expected interactions and results
        mock_works_deposits.assert_called_once_with(
            "integration_user", "https://works.hcommons.org"
        )
        self.assertEqual(result, mock_instance)
        self.assertEqual(result.name, "Mocked WorksDeposits Instance")

        # Call again and verify caching
        result2 = await self.model_instance.works_deposits
        self.assertEqual(result, result2)
        mock_works_deposits.assert_called_once()


class WpUserPropertyTests(django.test.TestCase):
    """Tests for the wp_user cached property."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create the model instance
        self.model_instance, self.user = set_up_api_instance()
        self.model_instance.user = "test_wordpress_user"

        # Set _wp_user to None as it would be in the real class
        self.model_instance._wp_user = None

        # Create a mock for WpUser.objects.get
        self.wp_user_get_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpUser.objects.get"
        )
        self.mock_wp_user_get = self.wp_user_get_patcher.start()

        # Create a mock WpUser instance
        self.mock_wp_user = mock.MagicMock()
        self.mock_wp_user.ID = 123
        self.mock_wp_user.user_email = "test@example.com"

        # Set up the mock to return our mock WpUser
        self.mock_wp_user_get.return_value = self.mock_wp_user

    def tearDown(self):
        """Clean up after the tests."""
        self.wp_user_get_patcher.stop()

    def test_wp_user_initialization(self):
        """Test that wp_user retrieves a WpUser if _wp_user is None."""
        # Call the property
        result = self.model_instance.wp_user

        # Assert WpUser.objects.get was called with correct parameters
        self.mock_wp_user_get.assert_called_once_with(
            user_login=self.model_instance.user
        )

        # Assert the result is the mock WpUser instance
        self.assertEqual(result, self.mock_wp_user)

        # Assert that _wp_user is now set
        self.assertIsNotNone(self.model_instance._wp_user)
        self.assertEqual(self.model_instance._wp_user, self.mock_wp_user)

    def test_wp_user_caching(self):
        """Test that wp_user caches the user and doesn't query again."""
        # Call the property twice
        result1 = self.model_instance.wp_user
        result2 = self.model_instance.wp_user

        # Assert WpUser.objects.get was called only once
        self.mock_wp_user_get.assert_called_once()

        # Assert both results are the same
        self.assertEqual(result1, result2)
        self.assertEqual(result1, self.mock_wp_user)

    def test_wp_user_with_existing_instance(self):
        """Test that wp_user returns existing _wp_user if available."""
        # Set up an existing _wp_user
        existing_wp_user = mock.MagicMock()
        existing_wp_user.ID = 456
        existing_wp_user.user_email = "existing@example.com"

        self.model_instance._wp_user = existing_wp_user

        # Call the property
        result = self.model_instance.wp_user

        # Assert WpUser.objects.get was not called
        self.mock_wp_user_get.assert_not_called()

        # Assert the result is the existing instance
        self.assertEqual(result, existing_wp_user)
        self.assertEqual(result.ID, 456)

    def test_missing_user_attribute(self):
        """Test behavior when the user attribute is missing."""
        # Remove user attribute
        delattr(self.model_instance, "user")

        # Call the property and expect an exception
        with self.assertRaises(AttributeError):
            _ = self.model_instance.wp_user

    def test_wp_user_not_found(self):
        """Test handling when WpUser.objects.get raises ObjectDoesNotExist."""
        # Set up the mock to raise ObjectDoesNotExist
        self.mock_wp_user_get.side_effect = ObjectDoesNotExist(
            "WpUser matching query does not exist."
        )

        # Call the property and expect the exception to be propagated
        with self.assertRaises(ObjectDoesNotExist) as context:
            _ = self.model_instance.wp_user

        # Assert the error message is as expected
        self.assertIn(
            "WpUser matching query does not exist", str(context.exception)
        )

        # Assert that _wp_user is still None
        self.assertIsNone(self.model_instance._wp_user)

    def test_wp_user_database_error(self):
        """Test handling when WpUser.objects.get raises a database error."""
        # Set up the mock to raise a database error
        self.mock_wp_user_get.side_effect = Exception(
            "Database connection error"
        )

        # Call the property and expect the exception to be propagated
        with self.assertRaises(Exception) as context:
            _ = self.model_instance.wp_user

        # Assert the error message is as expected
        self.assertEqual(str(context.exception), "Database connection error")

        # Assert that _wp_user is still None
        self.assertIsNone(self.model_instance._wp_user)


class MastodonPostsPropertyTests(django.test.TestCase):
    """
    Tests for the mastodon_posts property
    """

    def setUp(self):
        """
        Set up test data
        :return:
        """
        # Create the model instance placeholder
        self.model_instance = None
        self.user = None

    def test_mastodon_posts_property(self):
        """
        Test the mastodon_posts property
        :return:
        """
        with mock.patch(
            "knowledge_commons_profiles.newprofile.api.API.mastodon_profile",
            new_callable=mock.PropertyMock,
        ) as mock_last_transaction:
            mock_last_transaction.return_value = None

            self.model_instance, self.user = set_up_api_instance()

            self.model_instance._mastodon_posts = "TEST"

            self.assertEqual(self.model_instance.mastodon_posts, "TEST")

            mock_last_transaction.assert_called_once()


class MastodonProfileParsingTests(django.test.TestCase):
    """Tests focused on the parsing logic in the mastodon_profile property."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Reset instance variables
        self.model_instance._mastodon_profile = None
        self.model_instance.mastodon_username = None
        self.model_instance.mastodon_server = None
        self.model_instance._mastodon_posts = None

        # Create a mock for the MastodonFeed class
        self.mastodon_feed_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.mastodon.MastodonFeed"
        )
        self.mock_mastodon_feed = self.mastodon_feed_patcher.start()

        self.user_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.User.objects.get"
        )
        self.mock_user_patcher = self.user_patcher.start()
        self.mock_user_patcher.return_value = self.user

        self.profile_creator_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.Profile.objects.create"
        )
        self.mock_user_creator_patcher = self.profile_creator_patcher.start()

        # Create a mock MastodonFeed instance
        self.mock_feed_instance = mock.MagicMock()
        self.mock_mastodon_feed.return_value = self.mock_feed_instance

    def tearDown(self):
        """Clean up after the tests."""
        self.mastodon_feed_patcher.stop()
        self.user_patcher.stop()
        self.profile_creator_patcher.stop()

    def test_standard_mastodon_handle_parsing(self):
        """Test parsing of a standard Mastodon handle (@username@server.com)."""
        # Set up profile_info with a standard Mastodon handle
        self.model_instance._profile_info = {
            "mastodon": "@testuser@mastodon.social"
        }

        # Call the property
        result = self.model_instance.mastodon_profile

        # Assert the profile is returned correctly
        self.assertEqual(result, "@testuser@mastodon.social")

        # Assert username and server are parsed correctly
        self.assertEqual(self.model_instance.mastodon_username, "testuser")
        self.assertEqual(
            self.model_instance.mastodon_server, "mastodon.social"
        )

        # Assert MastodonFeed was initialized with correct parameters
        self.mock_mastodon_feed.assert_called_once_with(
            "testuser", "mastodon.social"
        )

    def test_complex_server_domain_parsing(self):
        """Test parsing with complex server domains (subdomain, multiple
        dots)."""
        # Set up profile_info with a complex server domain
        self.model_instance._profile_info = {
            "mastodon": "@user@social.example.co.uk"
        }

        # Call the property
        _ = self.model_instance.mastodon_profile

        # Assert username and server are parsed correctly
        self.assertEqual(self.model_instance.mastodon_username, "user")
        self.assertEqual(
            self.model_instance.mastodon_server, "social.example.co.uk"
        )

        # Assert MastodonFeed was initialized with correct parameters
        self.mock_mastodon_feed.assert_called_once_with(
            "user", "social.example.co.uk"
        )

    def test_username_with_dots_and_underscores(self):
        """Test parsing with username containing dots and underscores."""
        # Set up profile_info with username containing dots and underscores
        self.model_instance._profile_info = {
            "mastodon": "@user.name_123@mastodon.social"
        }

        # Call the property
        _ = self.model_instance.mastodon_profile

        # Assert username and server are parsed correctly
        self.assertEqual(
            self.model_instance.mastodon_username, "user.name_123"
        )
        self.assertEqual(
            self.model_instance.mastodon_server, "mastodon.social"
        )

    def test_empty_mastodon_profile(self):
        """Test behavior when mastodon profile is empty."""
        # Set up profile_info with empty mastodon field
        self.model_instance._profile_info = {"mastodon": ""}

        # Call the property
        result = self.model_instance.mastodon_profile

        # Assert the empty profile is returned
        self.assertEqual(result, "")

        # Assert MastodonFeed was not initialized
        self.mock_mastodon_feed.assert_not_called()

        # Assert username and server remain None
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_none_mastodon_profile(self):
        """Test behavior when mastodon profile is None."""
        # Set up profile_info with None mastodon field
        self.model_instance._profile_info = {"mastodon": None}

        # Call the property
        result = self.model_instance.mastodon_profile

        # Assert None is returned
        self.assertIsNone(result)

        # Assert MastodonFeed was not initialized
        self.mock_mastodon_feed.assert_not_called()

        # Assert username and server remain None
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_invalid_format_no_at_symbol(self):
        """Test behavior with an invalid format (missing @ symbol)."""
        # Set up profile_info with invalid format (no @ symbol)
        self.model_instance._profile_info = {
            "mastodon": "testuser.mastodon.social"
        }

        _ = self.model_instance.mastodon_profile

        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_invalid_format_too_many_at_symbols(self):
        """Test behavior with an invalid format (too many @ symbols)."""
        # Set up profile_info with invalid format (too many @ symbols)
        self.model_instance._profile_info = {
            "mastodon": "@test@user@mastodon.social"
        }

        # Call the property
        _ = self.model_instance.mastodon_profile

        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_missing_mastodon_key_in_profile_info(self):
        """Test behavior when 'mastodon' key is missing from profile_info."""
        # Set up profile_info without 'mastodon' key
        self.model_instance._profile_info = {"email": "test@example.com"}

        # Call the property and expect KeyError
        with self.assertRaises(KeyError):
            _ = self.model_instance.mastodon_profile

    def test_format_without_leading_at(self):
        """Test behavior when the mastodon handle doesn't have a leading @."""
        # Set up profile_info with handle without leading @
        self.model_instance._profile_info = {
            "mastodon": "testuser@mastodon.social"
        }

        # Call the property
        _ = self.model_instance.mastodon_profile

        # Due to the [1:] slice, it will miss the first character
        self.assertEqual(self.model_instance.mastodon_username, "testuser")
        self.assertEqual(
            self.model_instance.mastodon_server, "mastodon.social"
        )


class MastodonUserAndServerTests(django.test.TestCase):
    """Tests for the mastodon_user_and_server property."""

    def setUp(self):
        """Set up test data and mocks."""

        self.model_instance, self.user = set_up_api_instance()

        # Create a mock profile object
        self.mock_profile = mock.MagicMock()
        self.model_instance.profile = self.mock_profile

        # Reset instance variables that might be set by the property
        self.model_instance.mastodon_username = None
        self.model_instance.mastodon_server = None

    def test_empty_string_mastodon_field(self):
        """Test that an empty string triggers the final return None, None."""
        # Call the method with an empty string that has the correct number of
        # @ signs. This will pass the string validation and @ count
        # validation, but fail at the final if statement.
        # Creating a string with 2 @ signs but is still "falsy" in the
        # final if condition
        mastodon_field = "@@"  # This has 2 @ signs but will evaluate as
        # falsy in the context

        # Call the method
        username, server = self.model_instance._get_mastodon_user_and_server(
            mastodon_field
        )

        # Assert the final return line was hit (both values are None)
        self.assertIsNone(username)
        self.assertIsNone(server)

        # Verify instance variables weren't set
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_standard_mastodon_handle(self):
        """Test parsing of a standard Mastodon handle (@username@server.com)"""
        # Set up profile with a standard Mastodon handle
        self.mock_profile.mastodon = "@testuser@mastodon.social"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert username and server are parsed correctly
        self.assertEqual(username, "testuser")
        self.assertEqual(server, "mastodon.social")

        # Assert instance variables are set correctly
        self.assertEqual(self.model_instance.mastodon_username, "testuser")
        self.assertEqual(
            self.model_instance.mastodon_server, "mastodon.social"
        )

    def test_standard_mastodon_handle_with_bad_domain(self):
        """Test parsing of a standard Mastodon handle with a bad domain"""
        # Set up profile with a standard Mastodon handle
        self.mock_profile.mastodon = "@testuser@HAHAHA-THIS-IS-NOT_A_DOMAIN"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert username and server are parsed correctly
        self.assertIsNone(username)
        self.assertIsNone(server)

        # Assert instance variables are set correctly
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_complex_server_domain(self):
        """Test parsing with complex server domains (subdomain, multiple
        dots)."""
        # Set up profile with a complex server domain
        self.mock_profile.mastodon = "@user@social.example.co.uk"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert username and server are parsed correctly
        self.assertEqual(username, "user")
        self.assertEqual(server, "social.example.co.uk")

        # Assert instance variables are set correctly
        self.assertEqual(self.model_instance.mastodon_username, "user")
        self.assertEqual(
            self.model_instance.mastodon_server, "social.example.co.uk"
        )

    def test_username_with_special_characters(self):
        """Test parsing with username containing special characters."""
        # Set up profile with username containing dots and underscores
        self.mock_profile.mastodon = "@user.name_123@mastodon.social"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert username and server are parsed correctly
        self.assertEqual(username, "user.name_123")
        self.assertEqual(server, "mastodon.social")

        # Assert instance variables are set correctly
        self.assertEqual(
            self.model_instance.mastodon_username, "user.name_123"
        )
        self.assertEqual(
            self.model_instance.mastodon_server, "mastodon.social"
        )

    def test_empty_mastodon_profile(self):
        """Test behavior when mastodon profile is empty."""
        # Set up profile with empty mastodon field
        self.mock_profile.mastodon = ""

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert None values are returned
        self.assertIsNone(username)
        self.assertIsNone(server)

        # Assert instance variables remain None
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_none_mastodon_profile(self):
        """Test behavior when mastodon profile is None."""
        # Set up profile with None mastodon field
        self.mock_profile.mastodon = None

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Assert None values are returned
        self.assertIsNone(username)
        self.assertIsNone(server)

        # Assert instance variables remain None
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_invalid_format_no_at_symbol(self):
        """Test behavior with an invalid format (missing @ symbol)."""
        # Set up profile with invalid format (no @ symbol)
        self.mock_profile.mastodon = "testuser.mastodon.social"

        _ = self.model_instance.mastodon_user_and_server

        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)

    def test_invalid_format_too_many_at_symbols(self):
        """Test behavior with an invalid format (too many @ symbols)."""
        # Set up profile with invalid format (too many @ symbols)
        self.mock_profile.mastodon = "@test@user@mastodon.social"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        # Due to the split behavior, it will get the first part after @
        self.assertIsNone(username)

        # And the server will have extra parts
        self.assertIsNone(server)

    def test_format_without_leading_at(self):
        """Test behavior when the mastodon handle doesn't have a leading @."""
        # Set up profile with handle without leading @
        self.mock_profile.mastodon = "testuser@mastodon.social"

        # Call the property
        username, server = self.model_instance.mastodon_user_and_server

        self.assertEqual(username, "testuser")
        self.assertEqual(server, "mastodon.social")

    def test_missing_profile_attribute(self):
        """Test behavior when the profile attribute is missing."""
        # Remove profile attribute
        delattr(self.model_instance, "profile")

        # Call the property and expect an exception
        with self.assertRaises(django.http.response.Http404):
            _ = self.model_instance.mastodon_user_and_server

    def test_falsey_mastodon_value(self):
        """Test behavior with falsey values that aren't None or empty
        string."""
        # Test with False
        self.mock_profile.mastodon = False
        username, server = self.model_instance.mastodon_user_and_server
        self.assertIsNone(username)
        self.assertIsNone(server)

        # Test with 0
        self.mock_profile.mastodon = 0
        username, server = self.model_instance.mastodon_user_and_server
        self.assertIsNone(username)
        self.assertIsNone(server)


class ProfileInfoPropertyTests(django.test.TestCase):
    """Tests for the profile_info property."""

    def setUp(self):
        self.model_instance, self.user = set_up_api_instance()

        # Create a patch for the get_profile_info method
        self.get_profile_info_patcher = mock.patch.object(
            self.model_instance, "get_profile_info"
        )
        self.mock_get_profile_info = self.get_profile_info_patcher.start()

        # Define a sample profile info that would be set by get_profile_info
        self.sample_profile_info = {
            "username": "test_user",
            "email": "test@example.com",
            "name": "Test User",
        }

        # Configure the mock to set _profile_info when called
        def side_effect():
            self.model_instance._profile_info = self.sample_profile_info

        self.mock_get_profile_info.side_effect = side_effect

    def tearDown(self):
        """Clean up after the tests."""
        self.get_profile_info_patcher.stop()

    def test_profile_info_uncached(self):
        """Test that profile_info calls get_profile_info when
        _profile_info is None."""
        # Ensure _profile_info is None
        self.model_instance._profile_info = None

        # Call the property
        result = self.model_instance.profile_info

        # Assert get_profile_info was called
        self.mock_get_profile_info.assert_called_once()

        # Assert the result is what was set by our mocked get_profile_info
        self.assertEqual(result, self.sample_profile_info)

    def test_profile_info_cached(self):
        """Test that profile_info returns cached value without calling
        get_profile_info."""
        # Set a pre-existing _profile_info
        cached_profile_info = {
            "username": "cached_user",
            "email": "cached@example.com",
            "name": "Cached User",
        }
        self.model_instance._profile_info = cached_profile_info

        # Call the property
        result = self.model_instance.profile_info

        # Assert get_profile_info was NOT called
        self.mock_get_profile_info.assert_not_called()

        # Assert the result is the cached value
        self.assertEqual(result, cached_profile_info)


class ProfilePropertyTests(django.test.TestCase):
    """Tests for the profile property."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()
        self.model_instance.user = "test_user"
        self.model_instance._profile = None
        self.model_instance.create = True

        # Patch Profile.objects.prefetch_related to return a mock query manager
        self.prefetch_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.Profile.objects."
            "prefetch_related"
        )
        self.mock_prefetch = self.prefetch_patcher.start()

        # Configure the mock query manager to raise DoesNotExist when get()
        # is called
        self.mock_query_manager = mock.MagicMock()
        self.mock_prefetch.return_value = self.mock_query_manager

        self.mock_query_manager.get.return_value = self.mock_query_manager
        self.mock_query_manager.get.side_effect = Profile.DoesNotExist

        # Patch Profile.objects.create to use our factory
        self.create_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.Profile.objects.create"
        )
        self.mock_create = self.create_patcher.start()

        # Make create return a ProfileFactory instance
        self.mock_create.return_value = lambda **kwargs: ProfileFactory(
            **kwargs
        )

        # Patch User.objects.get to avoid it being called
        self.user_get_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.User.objects.get"
        )
        self.mock_user_get = self.user_get_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.prefetch_patcher.stop()
        self.create_patcher.stop()
        self.user_get_patcher.stop()

    def test_profile_creation_with_create_flag(self):
        """Test profile creation when profile doesn't exist and create
        flag is True."""
        # Call the property
        profile = self.model_instance.profile

        # Verify that prefetch_related().get() was called with the
        # correct username
        self.mock_query_manager.get.assert_called_once_with(
            username="test_user"
        )

        # Verify that User.objects.get was NOT called
        self.mock_user_get.assert_not_called()

        # Verify that Profile.objects.create was called with just the username
        self.mock_create.assert_called_once_with(username="test_user")

        # Verify the profile was set on the model instance
        self.assertIsNotNone(self.model_instance._profile)
        self.assertEqual(self.model_instance._profile, profile)


class GetProfileInfoTests(django.test.TestCase):
    """Tests for the get_profile_info method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Create a mock profile with all the required attributes
        self.mock_profile = mock.MagicMock()
        self.mock_profile.name = "Test User"
        self.mock_profile.username = "testuser"
        self.mock_profile.title = "Professor"
        self.mock_profile.affiliation = "Test University"
        self.mock_profile.twitter = "@testuser"
        self.mock_profile.github = "testuser"
        self.mock_profile.email = "test@example.com"
        self.mock_profile.orcid = "0000-0000-0000-0000"
        self.mock_profile.mastodon = "@testuser@mastodon.social"
        self.mock_profile.profile_image = "https://example.com/profile.jpg"
        self.mock_profile.works_username = "works_testuser"
        self.mock_profile.publications = "<p>Sample publication</p>"
        self.mock_profile.projects = "Sample project"
        self.mock_profile.memberships = "Sample membership"
        self.mock_profile.institutional_or_other_affiliation = (
            "Test Institution"
        )

        # Assign the mock profile to the model instance
        self.model_instance.profile = self.mock_profile

        # Mock the mastodon_user_and_server property
        mastodon_patcher = mock.patch.object(
            self.model_instance.__class__,
            "mastodon_user_and_server",
            new_callable=mock.PropertyMock,
        )
        self.mock_mastodon = mastodon_patcher.start()
        self.mock_mastodon.return_value = ("testuser", "mastodon.social")
        self.addCleanup(mastodon_patcher.stop)

        # Reset _profile_info to None
        self.model_instance._profile_info = None

    def test_get_profile_info_standard_case(self):
        """Test that get_profile_info returns the correct profile
        information."""
        # Call the method
        result = self.model_instance.get_profile_info()

        # Assert that the mastodon_user_and_server property was accessed
        self.mock_mastodon.assert_called_once()

        # Assert that the result contains the expected fields with correct
        # values
        self.helper_check_profile_info(result)

        # Assert that _profile_info was set on the model instance
        self.assertEqual(self.model_instance._profile_info, result)

    def helper_check_profile_info(self, result):
        self.assertEqual(result["name"], "Test User")
        self.assertEqual(result["username"], "testuser")
        self.assertEqual(result["title"], "Professor")
        self.assertEqual(result["affiliation"], "Test University")
        self.assertEqual(result["twitter"], "@testuser")
        self.assertEqual(result["github"], "testuser")
        self.assertEqual(result["email"], "test@example.com")
        self.assertEqual(result["orcid"], "0000-0000-0000-0000")
        self.assertEqual(result["mastodon"], "@testuser@mastodon.social")
        self.assertEqual(result["mastodon_username"], "testuser")
        self.assertEqual(result["mastodon_server"], "mastodon.social")
        self.assertEqual(
            result["profile_image"], "https://example.com/profile.jpg"
        )
        self.assertEqual(result["works_username"], "works_testuser")
        self.assertEqual(result["publications"], "<p>Sample publication</p>")
        self.assertEqual(result["projects"], "Sample project")
        self.assertEqual(result["memberships"], "Sample membership")
        self.assertEqual(
            result["institutional_or_other_affiliation"], "Test Institution"
        )

    def test_get_profile_info_with_missing_profile_attributes(self):
        """Test that get_profile_info handles missing profile attributes."""
        # Remove some attributes from the profile
        delattr(self.mock_profile, "title")
        delattr(self.mock_profile, "orcid")

        # Call the method and expect AttributeError
        with self.assertRaises(AttributeError):
            self.model_instance.get_profile_info()

    def test_get_profile_info_with_null_mastodon_data(self):
        """Test that get_profile_info handles null mastodon user and server."""
        # Configure the mock to return None, None
        self.mock_mastodon.return_value = (None, None)

        # Call the method
        result = self.model_instance.get_profile_info()

        # Assert that the mastodon fields have the expected values
        self.assertEqual(
            result["mastodon"], "@testuser@mastodon.social"
        )  # Original value
        self.assertIsNone(result["mastodon_username"])
        self.assertIsNone(result["mastodon_server"])


class GetBlogPostsTests(django.test.TestCase):
    """Tests for the get_blog_posts method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Set the required attributes
        self.model_instance.use_wordpress = True
        self.model_instance.user = "test_user"

        # Create a mock wp_user
        self.mock_wp_user = mock.MagicMock()
        self.mock_wp_user.id = 42
        self.model_instance.wp_user = self.mock_wp_user

        # Mock cache.get and cache.set
        self.cache_get_patcher = mock.patch("django.core.cache.cache.get")
        self.mock_cache_get = self.cache_get_patcher.start()
        self.mock_cache_get.return_value = None  # Default to cache miss

        self.cache_set_patcher = mock.patch("django.core.cache.cache.set")
        self.mock_cache_set = self.cache_set_patcher.start()

        # Mock database cursor
        self.cursor_mock = mock.MagicMock()
        self.connection_mock = mock.MagicMock()
        self.connection_mock.cursor.return_value.__enter__.return_value = (
            self.cursor_mock
        )

        self.connections_patcher = mock.patch.dict(
            "django.db.connections", {"wordpress_dev": self.connection_mock}
        )

        self.mock_connections = self.connections_patcher.start()

        # Mock WpBlog.objects.values_list
        self.wpblog_values_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpBlog.objects."
            "values_list"
        )
        self.mock_wpblog_values = self.wpblog_values_patcher.start()

        # Mock WpPostSubTable.objects.raw
        self.wppost_raw_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpPostSubTable."
            "objects.raw"
        )
        self.mock_wppost_raw = self.wppost_raw_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.cache_get_patcher.stop()
        self.cache_set_patcher.stop()
        self.connections_patcher.stop()
        self.wpblog_values_patcher.stop()
        self.wppost_raw_patcher.stop()

    def test_use_wordpress_false(self):
        """Test that an empty list is returned when use_wordpress is False."""
        self.model_instance.use_wordpress = False

        result = self.model_instance.get_blog_posts()

        self.assertEqual(result, [])
        self.mock_cache_get.assert_not_called()
        self.cursor_mock.execute.assert_not_called()

    def test_cached_response(self):
        """Test that cached response is returned when available."""
        # Set up mock to return a cached response
        cached_posts = [mock.MagicMock(), mock.MagicMock()]
        self.mock_cache_get.return_value = cached_posts

        result = self.model_instance.get_blog_posts()

        # Check cache was queried with correct key
        self.mock_cache_get.assert_called_once_with(
            f"blog_post_list-{self.model_instance.user}",
            version=newprofile.__version__,
        )

        # Check result is the cached response
        self.assertEqual(result, cached_posts)

        # Check no database queries were made
        self.cursor_mock.execute.assert_not_called()
        self.mock_wpblog_values.assert_not_called()
        self.mock_wppost_raw.assert_not_called()

    def test_sql_generation_no_blogs(self):
        """Test SQL generation when no blogs are found."""
        # Set up mocks to return no blogs
        self.cursor_mock.fetchall.return_value = []
        self.mock_wpblog_values.return_value = []

        result = self.model_instance.get_blog_posts()

        # Check correct SQL was executed
        self.cursor_mock.execute.assert_called_once_with("SHOW TABLES;")

        # Check WpBlog.objects.values_list was called correctly
        self.mock_wpblog_values.assert_called_once_with("blog_id", flat=True)

        # Check WpPostSubTable.objects.raw was not called (no valid blogs)
        self.mock_wppost_raw.assert_not_called()

        # Check result is empty
        self.assertEqual(result, [])

        # Check cache was set with empty result
        self.mock_cache_set.assert_called_once_with(
            f"blog_post_list-{self.model_instance.user}",
            [],
            timeout=600,
            version=newprofile.__version__,
        )

    def test_sql_generation_with_blogs(self):
        """Test SQL generation with valid blogs."""
        # Set up mocks to return table list
        table_list = [
            ("wp_1_posts",),
            ("wp_1_options",),
            ("wp_2_posts",),
            ("wp_2_options",),
            ("wp_3_posts",),
            ("wp_3_options",),
            ("wp_blogs",),
            ("wp_other_table",),
        ]
        self.cursor_mock.fetchall.return_value = table_list

        # Set up mock to return blog IDs
        blog_ids = [1, 2, 3, 4]  # Note: 4 doesn't have matching tables
        self.mock_wpblog_values.return_value = blog_ids

        # Set up mock for raw query result
        mock_posts = [mock.MagicMock(), mock.MagicMock()]
        self.mock_wppost_raw.return_value = mock_posts

        result = self.model_instance.get_blog_posts()

        # Verify SHOW TABLES was executed
        self.cursor_mock.execute.assert_called_once_with("SHOW TABLES;")

        # Check raw query was called with correct SQL and parameters
        sql_arg = self.mock_wppost_raw.call_args[0][0]
        params_arg = self.mock_wppost_raw.call_args[0][1]

        # Check SQL contains expected parts
        self.assertIn("WITH unified_posts AS", sql_arg)
        self.assertIn("UNION ALL", sql_arg)

        # Check number of blog IDs that should be in query (3 valid blogs)
        self.assertEqual(
            sql_arg.count("blog_id") / 2, 3  # it's specified twice in the SQL
        )  # One per SELECT statement

        # Check number of parameters matches number of valid blogs
        self.assertEqual(len(params_arg), 3)
        self.assertEqual(
            params_arg, [42, 42, 42]
        )  # wp_user.id repeated for each blog

        # Check result is from raw query
        self.assertEqual(result, mock_posts)

        # Check cache was set with result
        self.mock_cache_set.assert_called_once_with(
            f"blog_post_list-{self.model_instance.user}",
            mock_posts,
            timeout=600,
            version=newprofile.__version__,
        )

    def test_sql_injection_prevention(self):
        """Test that non-digit blog IDs are filtered out to prevent SQL
        injection."""
        # Set up mocks
        table_list = [("wp_1_posts",), ("wp_1_options",), ("wp_blogs",)]
        self.cursor_mock.fetchall.return_value = table_list

        # Include a malicious blog ID
        blog_ids = [1, "2; DROP TABLE users; --"]
        self.mock_wpblog_values.return_value = blog_ids

        # Set up mock for raw query result
        mock_posts = [mock.MagicMock()]
        self.mock_wppost_raw.return_value = mock_posts

        self.model_instance.get_blog_posts()

        # Check raw query was called
        sql_arg = self.mock_wppost_raw.call_args[0][0]
        params_arg = self.mock_wppost_raw.call_args[0][1]

        # Only the valid blog ID should be included
        self.assertEqual(sql_arg.count("wp_1_posts"), 1)
        self.assertEqual(sql_arg.count("wp_2; DROP TABLE users; --"), 0)

        # Only one parameter should be passed (for the one valid blog)
        self.assertEqual(len(params_arg), 1)
        self.assertEqual(params_arg, [42])

    def test_collation_specifications(self):
        """Test that proper collation specifications are included in the
        SQL."""
        # Set up mocks
        table_list = [("wp_1_posts",), ("wp_1_options",), ("wp_blogs",)]
        self.cursor_mock.fetchall.return_value = table_list

        blog_ids = [1, 2]
        self.mock_wpblog_values.return_value = blog_ids

        self.model_instance.get_blog_posts()

        # Check SQL includes collation specifications
        sql_arg = self.mock_wppost_raw.call_args[0][0]

        # Check for collation on text fields
        self.assertIn("post_title COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("post_status COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("post_name COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("post_type COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("option_value COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("domain COLLATE utf8mb4_unicode_ci", sql_arg)
        self.assertIn("path COLLATE utf8mb4_unicode_ci", sql_arg)

    def test_limit_and_ordering(self):
        """Test that SQL includes proper ORDER BY and LIMIT clauses."""
        # Set up mocks
        table_list = [("wp_1_posts",), ("wp_1_options",), ("wp_blogs",)]
        self.cursor_mock.fetchall.return_value = table_list

        blog_ids = [1]
        self.mock_wpblog_values.return_value = blog_ids

        self.model_instance.get_blog_posts()

        # Check SQL includes ORDER BY and LIMIT
        sql_arg = self.mock_wppost_raw.call_args[0][0]

        self.assertIn("ORDER BY post_date DESC", sql_arg)
        self.assertIn("LIMIT 25", sql_arg)

    def test_post_status_and_type_filtering(self):
        """Test that SQL properly filters by post_status and post_type."""
        # Set up mocks
        table_list = [("wp_1_posts",), ("wp_1_options",), ("wp_blogs",)]
        self.cursor_mock.fetchall.return_value = table_list

        blog_ids = [1]
        self.mock_wpblog_values.return_value = blog_ids

        self.model_instance.get_blog_posts()

        # Check SQL includes proper filtering
        sql_arg = self.mock_wppost_raw.call_args[0][0]

        self.assertIn("p.post_status='publish'", sql_arg)
        self.assertIn("p.post_type='post'", sql_arg)


class GetAboutUserTests(django.test.TestCase):
    """Tests for the get_about_user method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Create a mock for the profile property
        self.profile_patcher = mock.patch.object(
            self.model_instance.__class__,
            "profile",
            new_callable=mock.PropertyMock,
        )
        self.mock_profile = self.profile_patcher.start()

        # Create a mock profile object that will be returned by the property
        self.profile_obj = mock.MagicMock()
        self.mock_profile.return_value = self.profile_obj

    def tearDown(self):
        """Clean up after the tests."""
        self.profile_patcher.stop()

    def test_get_about_user_standard_case(self):
        """Test that get_about_user returns the profile's about_user
        attribute."""
        # Set up mock profile with about_user attribute
        expected_about_user = "This is information about the test user."
        self.profile_obj.about_user = expected_about_user

        # Call the method
        result = self.model_instance.get_about_user()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result matches the profile's about_user
        self.assertEqual(result, expected_about_user)

    def test_get_about_user_empty_string(self):
        """Test that get_about_user handles empty about_user string."""
        # Set up mock profile with empty about_user
        self.profile_obj.about_user = ""

        # Call the method
        result = self.model_instance.get_about_user()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result is an empty string
        self.assertEqual(result, "")

    def test_get_about_user_none_value(self):
        """Test that get_about_user handles None value."""
        # Set up mock profile with None about_user
        self.profile_obj.about_user = None

        # Call the method
        result = self.model_instance.get_about_user()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result is None
        self.assertIsNone(result)

    def test_get_about_user_missing_attribute(self):
        """Test that get_about_user raises AttributeError when about_user
        is missing."""
        # Set up mock profile without about_user attribute
        del self.profile_obj.about_user

        # Call the method and expect AttributeError
        with self.assertRaises(AttributeError):
            self.model_instance.get_about_user()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()


class GetEducationTests(django.test.TestCase):
    """Tests for the get_education method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Create a mock for the profile property
        self.profile_patcher = mock.patch.object(
            self.model_instance.__class__,
            "profile",
            new_callable=mock.PropertyMock,
        )
        self.mock_profile = self.profile_patcher.start()

        # Create a mock profile object that will be returned by the property
        self.profile_obj = mock.MagicMock()
        self.mock_profile.return_value = self.profile_obj

    def tearDown(self):
        """Clean up after the tests."""
        self.profile_patcher.stop()

    def test_get_education_standard_case(self):
        """Test that get_about_user returns the profile's education
        attribute."""
        # Set up mock profile with education attribute
        expected_education = "This is information about the test user."
        self.profile_obj.education = expected_education

        # Call the method
        result = self.model_instance.get_education()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result matches the profile's education
        self.assertEqual(result, expected_education)

    def test_get_education_empty_string(self):
        """Test that get_education handles empty education string."""
        # Set up mock profile with empty about_user
        self.profile_obj.education = ""

        # Call the method
        result = self.model_instance.get_education()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result is an empty string
        self.assertEqual(result, "")

    def test_get_education_none_value(self):
        """Test that get_education handles None value."""
        # Set up mock profile with None about_user
        self.profile_obj.education = None

        # Call the method
        result = self.model_instance.get_education()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()

        # Assert the result is None
        self.assertIsNone(result)

    def test_get_education_missing_attribute(self):
        """Test that get_about_user raises AttributeError when education
        is missing."""
        # Set up mock profile without education attribute
        del self.profile_obj.education

        # Call the method and expect AttributeError
        with self.assertRaises(AttributeError):
            self.model_instance.get_education()

        # Assert that profile property was accessed
        self.mock_profile.assert_called_once()


class GetGroupsTests(django.test.TestCase):
    """Tests for the get_groups method."""

    def setUp(self):
        """Set up test data and mocks."""

        self.model_instance, self.user = set_up_api_instance()

        # Create a mock for wp_user with an ID
        self.model_instance.wp_user = mock.MagicMock()
        self.model_instance.wp_user.id = 42

        # Mock WpBpGroupMember.objects.filter
        self.filter_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api."
            "WpBpGroupMember.objects.filter"
        )
        self.mock_filter = self.filter_patcher.start()

        # Set up mock chain for the QuerySet methods
        self.mock_queryset = mock.MagicMock()
        self.mock_filter.return_value = self.mock_queryset

        # Mock for prefetch_related
        self.mock_prefetch = mock.MagicMock()
        self.mock_queryset.prefetch_related.return_value = self.mock_prefetch

        # Mock for order_by
        self.mock_order_by = mock.MagicMock()
        self.mock_prefetch.order_by.return_value = self.mock_order_by

        # Sample groups that will be returned by the query
        self.sample_groups = [
            mock.MagicMock(name="Group A"),
            mock.MagicMock(name="Group B"),
        ]

    def tearDown(self):
        """Clean up after the tests."""
        self.filter_patcher.stop()

    def test_get_groups_standard_case(self):
        """Test that get_groups returns the properly filtered and
        ordered groups."""
        # Set up the mock to return our sample groups
        self.mock_order_by.__iter__.return_value = self.sample_groups

        # Call the method
        result = self.model_instance.get_groups()

        # Assert that filter was called with the correct parameters
        self.mock_filter.assert_called_once_with(
            user_id=42,  # The ID of wp_user
            is_confirmed=True,
            group__status="public",
        )

        # Assert that prefetch_related was called with "group"
        self.mock_queryset.prefetch_related.assert_called_once_with("group")

        # Assert that order_by was called with "group__name"
        self.mock_prefetch.order_by.assert_called_once_with("group__name")

        # Assert the result is the expected list of groups
        self.assertEqual(result, self.mock_order_by)
        self.assertEqual(list(result), self.sample_groups)

    def test_get_groups_empty_result(self):
        """Test that get_groups handles empty results correctly."""
        # Set up the mock to return an empty list
        self.mock_order_by.__iter__.return_value = []

        # Call the method
        result = self.model_instance.get_groups()

        # Assert that the method chain was called correctly
        self.mock_filter.assert_called_once()
        self.mock_queryset.prefetch_related.assert_called_once()
        self.mock_prefetch.order_by.assert_called_once()

        # Assert the result is an empty list
        self.assertEqual(list(result), [])

    def test_get_groups_none_wp_user(self):
        """Test that get_groups raises AttributeError when wp_user is
        None."""
        # Set wp_user to None
        self.model_instance.wp_user = None

        # Call the method and expect AttributeError
        with self.assertRaises(AttributeError):
            self.model_instance.get_groups()

        # Assert that filter was not called
        self.mock_filter.assert_not_called()


class GetCoverImageTests(django.test.TestCase):
    """Tests for the get_cover_image method."""

    def setUp(self):
        """Set up test data and mocks."""

        self.model_instance, self.user = set_up_api_instance()

        # Mock the profile property
        self.profile_patcher = mock.patch.object(
            self.model_instance.__class__,
            "profile",
            new_callable=mock.PropertyMock,
        )
        self.mock_profile = self.profile_patcher.start()

        # Create a mock profile object
        self.profile_obj = mock.MagicMock()
        self.mock_profile.return_value = self.profile_obj

        # Mock the coverimage_set
        self.mock_coverimage_set = mock.MagicMock()
        self.profile_obj.coverimage_set = self.mock_coverimage_set

        # Mock WpUserMeta.objects.filter
        self.filter_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpUserMeta.objects."
            "filter"
        )
        self.mock_filter = self.filter_patcher.start()

        # Set up mock for filter().first()
        self.mock_queryset = mock.MagicMock()
        self.mock_filter.return_value = self.mock_queryset
        self.mock_user_meta = mock.MagicMock()
        self.mock_queryset.first.return_value = self.mock_user_meta

        # Mock phpserialize.unserialize
        self.phpserialize_patcher = mock.patch("phpserialize.unserialize")
        self.mock_phpserialize = self.phpserialize_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.profile_patcher.stop()
        self.filter_patcher.stop()
        self.phpserialize_patcher.stop()

    def test_get_cover_image_with_local_image(self):
        """Test when the user has a local cover image."""
        # Set up mock cover image
        mock_cover = mock.MagicMock()
        mock_cover.file_path = "/path/to/local/cover.jpg"
        self.mock_coverimage_set.first.return_value = mock_cover

        # Call the method
        result = self.model_instance.get_cover_image()

        # Assert that coverimage_set.first() was called
        self.mock_coverimage_set.first.assert_called_once()

        # Assert that WpUserMeta.objects.filter was not called (early return)
        self.mock_filter.assert_not_called()

        # Assert the result is the local file path
        self.assertEqual(result, "/path/to/local/cover.jpg")

        # Assert that phpserialize.unserialize was not called
        self.mock_phpserialize.assert_not_called()

    def test_get_cover_image_with_wordpress_image(self):
        """Test when the user has a WordPress cover image but no local
        image."""
        # Set up mock to return no local cover image
        self.mock_coverimage_set.first.return_value = None

        # Set up mock for WordPress metadata
        self.mock_user_meta.meta_value = "serialized_php_data"

        # Set up phpserialize mock
        wp_image_path = "/wp-content/uploads/cover.jpg"
        self.mock_phpserialize.return_value = {
            b"attachment": wp_image_path.encode()
        }

        # Call the method
        result = self.model_instance.get_cover_image()

        # Assert that coverimage_set.first() was called
        self.mock_coverimage_set.first.assert_called_once()

        # Assert that WpUserMeta.objects.filter was called with correct params
        self.mock_filter.assert_called_once_with(meta_key="_bb_cover_photo")
        self.mock_queryset.first.assert_called_once()

        # Assert that phpserialize.unserialize was called with correct args
        self.mock_phpserialize.assert_called_once_with(b"serialized_php_data")

        # Assert the result is the WordPress image path
        self.assertEqual(result, wp_image_path)

    def test_get_cover_image_no_local_or_wordpress_image(self):
        """Test when no cover image is found in either location."""
        # Set up mock to return no local cover image
        self.mock_coverimage_set.first.return_value = None

        # Set up mock to return no WordPress metadata
        self.mock_queryset.first.return_value = None

        # Call the method and expect AttributeError (trying to access
        # meta_value on None)
        with self.assertRaises(AttributeError):
            self.model_instance.get_cover_image()

        # Assert that coverimage_set.first() was called
        self.mock_coverimage_set.first.assert_called_once()

        # Assert that WpUserMeta.objects.filter was called
        self.mock_filter.assert_called_once()

        # Assert that phpserialize.unserialize was not called
        self.mock_phpserialize.assert_not_called()

    def test_get_cover_image_with_invalid_serialized_data(self):
        """Test handling of invalid PHP serialized data."""
        # Set up mock to return no local cover image
        self.mock_coverimage_set.first.return_value = None

        # Set up mock for WordPress metadata
        self.mock_user_meta.meta_value = "invalid_serialized_data"

        # Set up phpserialize mock to raise an exception
        self.mock_phpserialize.side_effect = Exception(
            "Invalid serialized data"
        )

        # Call the method and expect the exception to be propagated
        with self.assertRaises(Exception) as context:
            self.model_instance.get_cover_image()

        # Assert the exception message
        self.assertEqual(str(context.exception), "Invalid serialized data")

        # Assert that coverimage_set.first() was called
        self.mock_coverimage_set.first.assert_called_once()

        # Assert that WpUserMeta.objects.filter was called
        self.mock_filter.assert_called_once()

        # Assert that phpserialize.unserialize was called
        self.mock_phpserialize.assert_called_once()

    def test_get_cover_image_missing_attachment_key(self):
        """Test handling when 'attachment' key is missing in unserialized
        data."""
        # Set up mock to return no local cover image
        self.mock_coverimage_set.first.return_value = None

        # Set up mock for WordPress metadata
        self.mock_user_meta.meta_value = "serialized_php_data"

        # Set up phpserialize mock to return dict without 'attachment' key
        self.mock_phpserialize.return_value = {b"some_other_key": b"value"}

        # Call the method and expect KeyError
        with self.assertRaises(KeyError) as context:
            self.model_instance.get_cover_image()

        # Assert the KeyError is for the attachment key
        self.assertEqual(context.exception.args[0], b"attachment")


class GetProfilePhotoTests(django.test.TestCase):
    """Tests for the get_profile_photo method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Mock the profile property
        self.profile_patcher = mock.patch.object(
            self.model_instance.__class__,
            "profile",
            new_callable=mock.PropertyMock,
        )
        self.mock_profile = self.profile_patcher.start()

        # Create a mock profile object
        self.profile_obj = mock.MagicMock()
        self.mock_profile.return_value = self.profile_obj

        # Set the email on the profile
        self.profile_obj.email = "test@example.com"

        # Mock the profileimage_set
        self.mock_profileimage_set = mock.MagicMock()
        self.profile_obj.profileimage_set = self.mock_profileimage_set

    def tearDown(self):
        """Clean up after the tests."""
        self.profile_patcher.stop()

    def test_get_profile_photo_with_local_image(self):
        """Test when the user has a local profile image."""
        # Set up mock profile image
        mock_profile_image = mock.MagicMock()
        mock_profile_image.full = "/path/to/local/profile.jpg"
        self.mock_profileimage_set.first.return_value = mock_profile_image

        # Call the method
        result = self.model_instance.get_profile_photo()

        # Assert that profileimage_set.first() was called
        self.mock_profileimage_set.first.assert_called_once()

        # Assert the result is the local file path
        self.assertEqual(result, "/path/to/local/profile.jpg")

    def test_get_profile_photo_with_gravatar_fallback(self):
        """Test when the user has no local profile image and falls back
        to Gravatar."""
        # Set up mock to return no local profile image
        self.mock_profileimage_set.first.return_value = None

        # Set email for gravatar generation
        email = "test@example.com"
        size = 150

        # Manually calculate the expected gravatar URL
        email_encoded = email.lower().encode("utf-8")
        email_hash = hashlib.sha256(email_encoded).hexdigest()
        query_params = urlencode({"s": str(size)})
        expected_url = (
            f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"
        )

        # Call the method
        result = self.model_instance.get_profile_photo()

        # Assert that profileimage_set.first() was called
        self.mock_profileimage_set.first.assert_called_once()

        # Assert the result is the expected Gravatar URL
        self.assertEqual(result, expected_url)

    def test_get_profile_photo_email_case_insensitivity(self):
        """Test that the email is properly lowercased for Gravatar."""
        # Set up mock to return no local profile image
        self.mock_profileimage_set.first.return_value = None

        # Set mixed-case email for gravatar generation
        self.profile_obj.email = "Test@Example.COM"
        size = 150

        # Manually calculate the expected gravatar URL with lowercase email
        email_encoded = b"test@example.com"
        email_hash = hashlib.sha256(email_encoded).hexdigest()
        query_params = urlencode({"s": str(size)})
        expected_url = (
            f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"
        )

        # Call the method
        result = self.model_instance.get_profile_photo()

        # Assert the result is the expected Gravatar URL (using lowercase
        # email)
        self.assertEqual(result, expected_url)

    def test_get_profile_photo_no_email(self):
        """Test behavior when the profile has no email."""
        # Set up mock to return no local profile image
        self.mock_profileimage_set.first.return_value = None

        # Set empty email
        self.profile_obj.email = ""
        size = 150

        # Manually calculate the expected gravatar URL with empty email
        email_encoded = b""
        email_hash = hashlib.sha256(email_encoded).hexdigest()
        query_params = urlencode({"s": str(size)})
        expected_url = (
            f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"
        )

        # Call the method
        result = self.model_instance.get_profile_photo()

        # Assert the result is the expected Gravatar URL (using empty email)
        self.assertEqual(result, expected_url)

    def test_get_profile_photo_missing_email_attribute(self):
        """Test behavior when the profile has no email attribute."""
        # Set up mock to return no local profile image
        self.mock_profileimage_set.first.return_value = None

        # Remove email attribute
        delattr(self.profile_obj, "email")

        # Call the method and expect AttributeError
        with self.assertRaises(AttributeError):
            self.model_instance.get_profile_photo()


class GetMembershipsTests(django.test.TestCase):
    """Tests for the get_memberships method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Create a mock wp_user with ID
        self.model_instance.wp_user = mock.MagicMock()
        self.model_instance.wp_user.id = 42

        # Mock WpUserMeta.objects.filter
        self.filter_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpUserMeta.objects."
            "filter"
        )
        self.mock_filter = self.filter_patcher.start()

        # Set up mock for filter().first()
        self.mock_queryset = mock.MagicMock()
        self.mock_filter.return_value = self.mock_queryset
        self.mock_user_meta = mock.MagicMock()
        self.mock_queryset.first.return_value = self.mock_user_meta

        # Mock phpserialize.unserialize
        self.phpserialize_patcher = mock.patch("phpserialize.unserialize")
        self.mock_phpserialize = self.phpserialize_patcher.start()

        # Mock cache
        self.cache_get_patcher = mock.patch("django.core.cache.cache.get")
        self.mock_cache_get = self.cache_get_patcher.start()
        self.mock_cache_get.return_value = None  # Default to cache miss

        self.cache_set_patcher = mock.patch("django.core.cache.cache.set")
        self.mock_cache_set = self.cache_set_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.filter_patcher.stop()
        self.phpserialize_patcher.stop()
        self.cache_get_patcher.stop()
        self.cache_set_patcher.stop()

    def test_get_memberships_cached_response(self):
        """Test when cached response is available."""
        # Set up mock to return cached memberships
        cached_memberships = ["HASTAC", "MLA"]
        self.mock_cache_get.return_value = cached_memberships

        # Call the method
        result = self.model_instance.get_memberships()

        # Assert that cache.get was called with the correct key
        self.mock_cache_get.assert_called_once_with(
            f"user_memberships-{self.model_instance.user}",
            version=newprofile.__version__,
        )

        # Assert that WpUserMeta.objects.filter was not called (early return)
        self.mock_filter.assert_not_called()

        # Assert the result is the cached memberships
        self.assertEqual(result, cached_memberships)

    def test_get_memberships_standard_case(self):
        """Test successful extraction of memberships from metadata."""
        # Set up mock for WpUserMeta
        self.mock_user_meta.meta_value = "serialized_data"

        # Configure phpserialize to simulate double serialization
        serialized_inner = b"inner_serialized_data"
        self.mock_phpserialize.side_effect = [
            serialized_inner,  # First unserialize call
            {  # Second unserialize call
                b"item1": b"CO:COU:HASTAC:members:active",
                b"item2": b"CO:COU:MLA:members:active",
                b"item3": b"CO:COU:HC:members:active",
                # Should be filtered out
                b"item4": b"OTHER:FORMAT:members:active",
                # Should be filtered out
            },
        ]

        # Call the method
        result = self.model_instance.get_memberships()

        # Assert that WpUserMeta.objects.filter was called with correct params
        self.mock_filter.assert_called_once_with(
            meta_key="shib_ismemberof",
            user=self.model_instance.wp_user,
        )

        # Assert that phpserialize.unserialize was called twice
        self.assertEqual(self.mock_phpserialize.call_count, 2)

        # Assert that cache.set was called with correct params
        expected_memberships = ["HASTAC", "MLA"]
        self.mock_cache_set.assert_called_once_with(
            f"user_memberships-{self.model_instance.user}",
            expected_memberships,
            timeout=600,
            version=newprofile.__version__,
        )

        # Assert the result is the sorted list of valid memberships
        self.assertEqual(result, ["HASTAC", "MLA"])

    def test_get_memberships_no_metadata(self):
        """Test when no metadata is found."""
        # Set up mock to return no metadata
        self.mock_queryset.first.return_value = None

        # Call the method
        result = self.model_instance.get_memberships()

        # Assert that phpserialize.unserialize was not called
        self.mock_phpserialize.assert_not_called()

        # Assert that cache.set was not called
        self.mock_cache_set.assert_not_called()

        # Assert the result is an empty list
        self.assertEqual(result, [])

    def test_get_memberships_unserialize_exception(self):
        """Test handling of exception during unserialization."""
        # Set up mock for WpUserMeta
        self.mock_user_meta.meta_value = "invalid_serialized_data"

        # Configure phpserialize to raise an exception
        self.mock_phpserialize.side_effect = Exception(
            "Invalid serialized data"
        )

        # Call the method
        result = self.model_instance.get_memberships()

        # Assert that phpserialize.unserialize was called once
        self.mock_phpserialize.assert_called_once()

        # Assert that cache.set was not called
        self.mock_cache_set.assert_not_called()

        # Assert the result is an empty list
        self.assertEqual(result, [])

    def test_get_memberships_no_active_memberships(self):
        """Test when there are no active memberships in the expected
        format."""
        # Set up mock for WpUserMeta
        self.mock_user_meta.meta_value = "serialized_data"

        # Configure phpserialize to return no valid memberships
        serialized_inner = b"inner_serialized_data"
        self.mock_phpserialize.side_effect = [
            serialized_inner,  # First unserialize call
            {  # Second unserialize call - no valid memberships
                b"item1": b"OTHER:FORMAT:active",
                b"item2": b"CO:COU:HC:members:active",
                # Should be filtered out
                b"item3": b"CO:COU:TEST:not:active",  # Wrong format
            },
        ]

        # Call the method
        result = self.model_instance.get_memberships()

        # Assert that cache.set was called with an empty list
        self.mock_cache_set.assert_called_once_with(
            f"user_memberships-{self.model_instance.user}",
            [],
            timeout=600,
            version=newprofile.__version__,
        )

        # Assert the result is an empty list
        self.assertEqual(result, [])


class FollowerCountTests(django.test.TestCase):
    """Tests for the follower_count method."""

    def setUp(self):
        """Set up test data and mocks."""
        self.model_instance, self.user = set_up_api_instance()

        # Create a mock wp_user
        self.model_instance.wp_user = mock.MagicMock()
        self.model_instance.wp_user.id = 42

        # Mock WpBpFollow.objects.filter
        self.filter_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.api.WpBpFollow.objects."
            "filter"
        )
        self.mock_filter = self.filter_patcher.start()

        # Set up mock for filter().count()
        self.mock_queryset = mock.MagicMock()
        self.mock_filter.return_value = self.mock_queryset

    def tearDown(self):
        """Clean up after the tests."""
        self.filter_patcher.stop()

    def test_follower_count_standard_case(self):
        """Test that follower_count returns the correct count."""
        # Set up mock to return a count of 5 followers
        self.mock_queryset.count.return_value = 5

        # Call the method
        result = self.model_instance.follower_count()

        # Assert that filter was called with correct parameters
        self.mock_filter.assert_called_once_with(
            follower=self.model_instance.wp_user
        )

        # Assert that count was called
        self.mock_queryset.count.assert_called_once()

        # Assert the result is the expected count
        self.assertEqual(result, 5)

    def test_follower_count_zero_followers(self):
        """Test that follower_count returns 0 when there are no followers."""
        # Set up mock to return a count of 0 followers
        self.mock_queryset.count.return_value = 0

        # Call the method
        result = self.model_instance.follower_count()

        # Assert that filter was called with correct parameters
        self.mock_filter.assert_called_once_with(
            follower=self.model_instance.wp_user
        )

        # Assert that count was called
        self.mock_queryset.count.assert_called_once()

        # Assert the result is 0
        self.assertEqual(result, 0)
