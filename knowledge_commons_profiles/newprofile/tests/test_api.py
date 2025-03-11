import asyncio
from unittest import mock

import django.test
from django.core.exceptions import ObjectDoesNotExist
from django.test.client import RequestFactory

import knowledge_commons_profiles.newprofile.api
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    UserFactory,
)


class TestWorksHtmlPropertyTests(django.test.TransactionTestCase):
    """Tests for the works_html cached async property."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create a test user
        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )

        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )

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
        user = UserFactory(
            username="integrationuser",
            email="integration@example.com",
            password="integrationpass",
        )

        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        # Create a real model instance
        model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=user
        )

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

        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )
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
        # Create a model instance with real profile_info
        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )
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
        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )
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

            rf = RequestFactory()
            get_request = rf.get("/user/kfitz")

            self.user = UserFactory(
                username="testuser",
                email="test@example.com",
                password="testpass",
            )

            # Create the model instance
            self.model_instance = (
                knowledge_commons_profiles.newprofile.api.API(
                    request=get_request, user=self.user
                )
            )

            self.model_instance._mastodon_posts = "TEST"

            self.assertEqual(self.model_instance.mastodon_posts, "TEST")

            mock_last_transaction.assert_called_once()


class MastodonProfileParsingTests(django.test.TestCase):
    """Tests focused on the parsing logic in the mastodon_profile property."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create the model instance
        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        self.user = UserFactory(
            username="testuser",
            email="test@example.com",
            password="testpass",
        )

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )

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
        self.assertIsNone(self.model_instance.mastodon_username)
        self.assertIsNone(self.model_instance.mastodon_server)


class MastodonUserAndServerTests(django.test.TestCase):
    """Tests for the mastodon_user_and_server property."""

    def setUp(self):
        """Set up test data and mocks."""

        rf = RequestFactory()
        get_request = rf.get("/user/kfitz")

        self.user = UserFactory(
            username="testuser",
            email="test@example.com",
            password="testpass",
        )

        # Create the model instance
        self.model_instance = knowledge_commons_profiles.newprofile.api.API(
            request=get_request, user=self.user
        )

        # Create a mock profile object
        self.mock_profile = mock.MagicMock()
        self.model_instance.profile = self.mock_profile

        # Reset instance variables that might be set by the property
        self.model_instance.mastodon_username = None
        self.model_instance.mastodon_server = None

    def test_standard_mastodon_handle(self):
        """Test parsing of a standard Mastodon handle (@username@server.com)."""
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

        self.assertIsNone(username)
        self.assertIsNone(server)

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
