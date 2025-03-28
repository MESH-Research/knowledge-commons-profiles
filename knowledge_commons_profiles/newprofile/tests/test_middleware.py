import datetime
import hashlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.newprofile.middleware import (
    WordPressAuthMiddleware,
)

User = get_user_model()


class WordPressAuthMiddlewareTests(TestCase):
    """Tests for the WordPressAuthMiddleware class."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create a request factory
        self.factory = RequestFactory()

        # Mock the get_response callable
        self.get_response_mock = mock.MagicMock()
        self.get_response_mock.return_value = "response"

        # Create middleware instance
        self.middleware = WordPressAuthMiddleware(self.get_response_mock)

        # Create a test user
        self.test_user = User.objects.create_user(
            username="wp_testuser",
            email="test@example.com",
            password="password123",
        )

        # Mock database connections
        self.cursor_mock = mock.MagicMock()
        self.connection_mock = mock.MagicMock()
        self.connection_mock.cursor.return_value.__enter__.return_value = (
            self.cursor_mock
        )

        self.connections_patcher = mock.patch.dict(
            "django.db.connections", {"wordpress_dev": self.connection_mock}
        )
        self.mock_connections = self.connections_patcher.start()

        # Mock phpserialize
        self.phpserialize_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.middleware."
            "phpserialize.unserialize"
        )
        self.mock_phpserialize = self.phpserialize_patcher.start()

        # Mock User.objects.get_or_create
        self.get_or_create_patcher = mock.patch.object(
            User.objects, "get_or_create"
        )
        self.mock_get_or_create = self.get_or_create_patcher.start()
        self.mock_get_or_create.return_value = (self.test_user, False)

        # Mock login
        self.login_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.middleware.login"
        )
        self.mock_login = self.login_patcher.start()

        # Mock logout
        self.logout_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.middleware.logout"
        )
        self.mock_logout = self.logout_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.connections_patcher.stop()
        self.phpserialize_patcher.stop()
        self.get_or_create_patcher.stop()
        self.login_patcher.stop()
        self.logout_patcher.stop()

    def test_call_no_cookie(self):
        """Test middleware call when no WordPress cookie is present."""
        # Create request with no cookies
        request = self.factory.get("/")
        request.user = mock.MagicMock()
        request.user.is_authenticated = False

        # Call middleware
        response = self.middleware(request)

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert login was not called
        self.mock_login.assert_not_called()

        # Assert the response is the expected one
        self.assertEqual(response, "response")

    def test_call_already_authenticated(self):
        """Test middleware call when the user is already authenticated."""
        # Create request with authenticated user
        request = self.factory.get("/")
        request.user = mock.MagicMock()
        request.user.is_authenticated = True

        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)

        request.session["wordpress_logged_in_123"] = "cookie_value"

        # Call middleware
        response = self.middleware(request)

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert login was not called
        self.mock_login.assert_not_called()

        # Assert the response is the expected one
        self.assertEqual(response, "response")

    def test_get_wordpress_cookie(self):
        """Test extraction of WordPress auth cookie from request."""
        # Create request with WordPress cookie
        request = self.factory.get("/")
        request.COOKIES = {
            "wordpress_logged_in_123": "wp_testuser|123456789|token|hmac",
            "some_other_cookie": "value",
        }

        # Call method
        cookie = WordPressAuthMiddleware.get_wordpress_cookie(request)

        # Assert the correct cookie value is returned
        self.assertEqual(cookie, "wp_testuser|123456789|token|hmac")

    def test_get_wordpress_cookie_urlencoded(self):
        """Test extraction of URL-encoded WordPress auth cookie."""
        # Create request with URL-encoded WordPress cookie
        request = self.factory.get("/")
        request.COOKIES = {
            "wordpress_logged_in_123": "wp_testuser%7C123456789%7Ctoken%7Chmac"
        }

        # Call method
        cookie = WordPressAuthMiddleware.get_wordpress_cookie(request)

        # Assert the correct cookie value is returned (decoded)
        self.assertEqual(cookie, "wp_testuser|123456789|token|hmac")

    def test_get_wordpress_cookie_not_found(self):
        """Test when no WordPress auth cookie is found."""
        # Create request with no WordPress cookie
        request = self.factory.get("/")
        request.COOKIES = {"some_other_cookie": "value"}

        # Call method
        cookie = WordPressAuthMiddleware.get_wordpress_cookie(request)

        # Assert None is returned
        self.assertIsNone(cookie)

    def test_get_wordpress_values_found(self):
        """Test getting WordPress user values when the user exists."""
        # Set up cursor to return user values
        self.cursor_mock.fetchone.return_value = (
            42,
            "test@example.com",
            "hashed_password",
        )

        # Call method
        result = WordPressAuthMiddleware.get_wordpress_values("wp_testuser")

        # Assert cursor.execute was called with the correct SQL and parameters
        self.cursor_mock.execute.assert_called_once()
        sql = self.cursor_mock.execute.call_args[0][0]
        params = self.cursor_mock.execute.call_args[0][1]

        self.assertIn("SELECT ID, user_email, user_pass", sql)
        self.assertIn("FROM wp_users", sql)
        self.assertIn("WHERE user_login = %s", sql)
        self.assertEqual(params, ["wp_testuser"])

        # Assert the result is the expected tuple
        self.assertEqual(result, (42, "test@example.com", "hashed_password"))

    def test_get_wordpress_values_not_found(self):
        """Test getting WordPress user values when the user doesn't exist."""
        # Set up cursor to return None
        self.cursor_mock.fetchone.return_value = None

        # Call method
        result = WordPressAuthMiddleware.get_wordpress_values(
            "nonexistent_user"
        )

        # Assert the result is None
        self.assertIsNone(result)

    def test_get_meta_value_found(self):
        """Test getting meta value when it exists."""
        # Set up cursor to return meta value
        self.cursor_mock.fetchone.return_value = ("serialized_meta_value",)

        # Set up phpserialize to return deserialized value
        deserialized_value = {b"key": b"value"}
        self.mock_phpserialize.return_value = deserialized_value

        # Call method
        result = WordPressAuthMiddleware.get_meta_value(42)

        # Assert cursor.execute was called with the correct SQL and parameters
        self.cursor_mock.execute.assert_called_once()
        sql = self.cursor_mock.execute.call_args[0][0]
        params = self.cursor_mock.execute.call_args[0][1]

        self.assertIn("SELECT meta_value", sql)
        self.assertIn("FROM wp_usermeta", sql)
        self.assertIn(
            "WHERE user_id = %s AND meta_key = 'session_tokens'", sql
        )
        self.assertEqual(params, [42])

        # Assert phpserialize.unserialize was called
        self.mock_phpserialize.assert_called_once_with(
            b"serialized_meta_value"
        )

        # Assert the result is the deserialized value
        self.assertEqual(result, deserialized_value)

    def test_get_meta_value_not_found(self):
        """Test getting meta value when it doesn't exist."""
        # Set up cursor to return None
        self.cursor_mock.fetchone.return_value = None

        # Call method
        result = WordPressAuthMiddleware.get_meta_value(42)

        # Assert the result is None
        self.assertIsNone(result)

        # Assert phpserialize.unserialize was not called
        self.mock_phpserialize.assert_not_called()

    def test_authenticate_wordpress_session_valid(self):
        """Test successful WordPress session authentication."""
        # Set up test data
        username = "wp_testuser"
        expiration = str(
            int(
                (
                    datetime.datetime.now(tz=datetime.UTC)
                    + datetime.timedelta(hours=1)
                ).timestamp()
            )
        )
        token = "valid_token"
        hmac = "hmac_value"
        cookie_value = f"{username}|{expiration}|{token}|{hmac}"

        # Hash the token as WordPress would
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Set up get_wordpress_values to return user data
        with mock.patch.object(
            self.middleware, "get_wordpress_values"
        ) as mock_get_values:
            mock_get_values.return_value = (
                42,
                "test@example.com",
                "hashed_password",
            )

            # Set up get_meta_value to return session data
            with mock.patch.object(
                self.middleware, "get_meta_value"
            ) as mock_get_meta:
                # Create session data with matching token hash and
                # non-expired time
                session_data = {
                    token_hash.encode(): {
                        b"expiration": int(expiration),
                        b"login": b"timestamp",
                        b"data": b"session_data",
                    }
                }
                mock_get_meta.return_value = session_data

                # Call method
                result = self.middleware.authenticate_wordpress_session(
                    cookie_value
                )

                # Assert User.objects.get_or_create was called with correct
                # parameters
                self.mock_get_or_create.assert_called_once_with(
                    username=username,
                    defaults={"email": "test@example.com", "is_active": True},
                )

                # Assert the result is the test user
                self.assertEqual(result, self.test_user)

    def test_authenticate_wordpress_session_expired(self):
        """Test WordPress session authentication with expired session."""
        # Set up test data
        username = "wp_testuser"
        # Set expiration to one hour ago
        expiration = str(
            int(
                (
                    datetime.datetime.now(tz=datetime.UTC)
                    - datetime.timedelta(hours=1)
                ).timestamp()
            )
        )
        token = "valid_token"
        hmac = "hmac_value"
        cookie_value = f"{username}|{expiration}|{token}|{hmac}"

        # Hash the token as WordPress would
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Set up get_wordpress_values to return user data
        with mock.patch.object(
            self.middleware, "get_wordpress_values"
        ) as mock_get_values:
            mock_get_values.return_value = (
                42,
                "test@example.com",
                "hashed_password",
            )

            # Set up get_meta_value to return session data
            with mock.patch.object(
                self.middleware, "get_meta_value"
            ) as mock_get_meta:
                # Create session data with matching token hash but expired time
                session_data = {
                    token_hash.encode(): {
                        b"expiration": int(expiration),
                        b"login": b"timestamp",
                        b"data": b"session_data",
                    }
                }
                mock_get_meta.return_value = session_data

                # Call method
                result = self.middleware.authenticate_wordpress_session(
                    cookie_value
                )

                # Assert User.objects.get_or_create was not called
                self.mock_get_or_create.assert_not_called()

                # Assert the result is None
                self.assertIsNone(result)

    def test_authenticate_wordpress_session_token_mismatch(self):
        """Test WordPress session authentication with mismatched token."""
        # Set up test data
        username = "wp_testuser"
        expiration = str(
            int(
                (
                    datetime.datetime.now(tz=datetime.UTC)
                    + datetime.timedelta(hours=1)
                ).timestamp()
            )
        )
        token = "valid_token"
        hmac = "hmac_value"
        cookie_value = f"{username}|{expiration}|{token}|{hmac}"

        # Different token hash than what's in the cookie
        different_token_hash = hashlib.sha256(b"different_token").hexdigest()

        # Set up get_wordpress_values to return user data
        with mock.patch.object(
            self.middleware, "get_wordpress_values"
        ) as mock_get_values:
            mock_get_values.return_value = (
                42,
                "test@example.com",
                "hashed_password",
            )

            # Set up get_meta_value to return session data
            with mock.patch.object(
                self.middleware, "get_meta_value"
            ) as mock_get_meta:
                # Create session data with non-matching token hash
                session_data = {
                    different_token_hash.encode(): {
                        b"expiration": int(expiration),
                        b"login": b"timestamp",
                        b"data": b"session_data",
                    }
                }
                mock_get_meta.return_value = session_data

                # Call method
                result = self.middleware.authenticate_wordpress_session(
                    cookie_value
                )

                # Assert User.objects.get_or_create was not called
                self.mock_get_or_create.assert_not_called()

                # Assert the result is None
                self.assertIsNone(result)

    def test_call_with_valid_wordpress_cookie(self):
        """Test full middleware call with valid WordPress cookie."""
        # Create request with WordPress cookie
        request = self.factory.get("/")
        request.user = mock.MagicMock()
        request.user.is_authenticated = False

        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        request.session.save()

        # Set up cookie value
        username = "wp_testuser"
        expiration = str(
            int(
                (
                    datetime.datetime.now(tz=datetime.UTC)
                    + datetime.timedelta(hours=1)
                ).timestamp()
            )
        )
        token = "valid_token"
        hmac = "hmac_value"
        cookie_value = f"{username}|{expiration}|{token}|{hmac}"
        request.COOKIES = {"wordpress_logged_in_123": cookie_value}

        # Mock authenticate_wordpress_session to return test user
        with mock.patch.object(
            self.middleware, "authenticate_wordpress_session"
        ) as mock_auth:
            mock_auth.return_value = self.test_user

            # Call middleware
            response = self.middleware(request)

            # Assert authenticate_wordpress_session was called with cookie value
            mock_auth.assert_called_once_with(cookie_value)

            # Assert login was called with request and test user
            self.mock_login.assert_called_once_with(request, self.test_user)

            # Assert get_response was called with the request
            self.get_response_mock.assert_called_once_with(request)

            # Assert the response is the expected one
            self.assertEqual(response, "response")

    def test_call_with_invalid_wordpress_cookie(self):
        """Test middleware call with invalid WordPress cookie."""
        # Create request with WordPress cookie
        request = self.factory.get("/")
        request.user = mock.MagicMock()
        request.user.is_authenticated = False
        request.COOKIES = {"wordpress_logged_in_123": "invalid_cookie_value"}

        # Mock authenticate_wordpress_session to return None
        with mock.patch.object(
            self.middleware, "authenticate_wordpress_session"
        ) as mock_auth:
            mock_auth.return_value = None

            # Call middleware
            response = self.middleware(request)

            # Assert authenticate_wordpress_session was called with cookie
            # value
            mock_auth.assert_called_once_with("invalid_cookie_value")

            # Assert login was not called
            self.mock_login.assert_not_called()

            # Assert get_response was called with the request
            self.get_response_mock.assert_called_once_with(request)

            # Assert the response is the expected one
            self.assertEqual(response, "response")

    def test_call_authenticated_without_cookie(self):
        """Test middleware logs out authenticated users when WordPress
        cookie is missing."""
        # Create request with authenticated user but no WordPress cookie
        request = self.factory.get("/")
        request.user = self.test_user

        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)

        # Setup session to indicate user was logged in via WordPress
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        request.session["wordpress_logged_in"] = True
        request.session.save()

        # Call middleware
        response = self.middleware(request)

        # Assert logout was called
        self.mock_login.assert_not_called()  # Login shouldn't be called
        self.mock_logout.assert_called_once_with(
            request
        )  # Logout should be called

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert the response is the expected one
        self.assertEqual(response, "response")

    def test_call_authenticated_with_invalid_cookie(self):
        """Test middleware logs out authenticated users when WordPress
        cookie is invalid."""
        # Create request with authenticated user and WordPress cookie
        request = self.factory.get("/")
        request.user = self.test_user

        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)

        request.COOKIES = {"wordpress_logged_in_123": "invalid_cookie_value"}

        # Setup session to indicate user was logged in via WordPress
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        request.session["wordpress_logged_in"] = True
        request.session.save()

        # Mock authenticate_wordpress_session to return None (invalid cookie)
        with mock.patch.object(
            self.middleware, "authenticate_wordpress_session"
        ) as mock_auth:
            mock_auth.return_value = None

            # Call middleware
            response = self.middleware(request)

            # Assert authenticate_wordpress_session was called with cookie
            # value
            mock_auth.assert_called_once_with("invalid_cookie_value")

            # Assert logout was called
            self.mock_logout.assert_called_once_with(request)

            # Assert get_response was called with the request
            self.get_response_mock.assert_called_once_with(request)

            # Assert the response is the expected one
            self.assertEqual(response, "response")

    def test_call_authenticated_with_expired_cookie(self):
        """Test middleware logs out authenticated users when WordPress
        session is expired."""
        # Set up test data for an expired cookie
        username = "wp_testuser"
        # Set expiration to one hour ago
        expiration = str(
            int(
                (
                    datetime.datetime.now(tz=datetime.UTC)
                    - datetime.timedelta(hours=1)
                ).timestamp()
            )
        )
        token = "expired_token"
        hmac = "hmac_value"
        cookie_value = f"{username}|{expiration}|{token}|{hmac}"

        # Create request with authenticated user and expired WordPress cookie
        request = self.factory.get("/")
        request.user = self.test_user

        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)

        request.COOKIES = {"wordpress_logged_in_123": cookie_value}

        # Setup session to indicate user was logged in via WordPress
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        request.session["wordpress_logged_in"] = True
        request.session.save()

        # Mock authenticate_wordpress_session with actual implementation
        # calling
        with mock.patch.object(
            self.middleware, "get_wordpress_values"
        ) as mock_get_values:
            mock_get_values.return_value = (
                42,
                "test@example.com",
                "hashed_password",
            )

            # Create an expired session
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            with mock.patch.object(
                self.middleware, "get_meta_value"
            ) as mock_get_meta:
                session_data = {
                    token_hash.encode(): {
                        b"expiration": int(expiration),
                        b"login": b"timestamp",
                        b"data": b"session_data",
                    }
                }
                mock_get_meta.return_value = session_data

                # Call middleware
                response = self.middleware(request)

                # Assert logout was called
                self.mock_logout.assert_called_once_with(request)

                # Assert get_response was called with the request
                self.get_response_mock.assert_called_once_with(request)

                # Assert the response is the expected one
                self.assertEqual(response, "response")

    def test_call_authenticated_user_not_from_wordpress(self):
        """Test middleware doesn't log out users who weren't authenticated
        via WordPress."""
        # Create request with authenticated user but not from WordPress
        request = self.factory.get("/")
        request.user = self.test_user

        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)

        # Setup session with no wordpress_logged_in flag
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        request.session.save()

        # Call middleware
        response = self.middleware(request)

        # Assert logout was not called
        self.mock_logout.assert_called_once()

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert the response is the expected one
        self.assertEqual(response, "response")

    def test_call_authenticated_user_not_superuser_without_wordpress_flag(
        self,
    ):
        """Test middleware logs out authenticated users without
        wordpress_logged_in flag who are not superusers."""
        # Create a regular authenticated user (not superuser)
        request = self.factory.get("/")
        request.user = self.test_user
        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)
        request.user.is_superuser = False  # Ensure user is not a superuser

        # Setup session without wordpress_logged_in flag
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        # Intentionally not setting request.session["wordpress_logged_in"]
        request.session.save()

        # Call middleware
        response = self.middleware(request)

        # Assert logout was called
        self.mock_logout.assert_called_once_with(request)

        # Assert session flag was set to False before logout
        self.assertEqual(request.session.get("wordpress_logged_in"), False)

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert the response is the expected one
        self.assertEqual(response, "response")

    def test_call_authenticated_superuser_without_wordpress_flag(self):
        """Test middleware does NOT log out superusers even without
        wordpress_logged_in flag."""
        # Create a superuser
        superuser = User.objects.create_superuser(
            username="admin_user",
            email="admin@example.com",
            password="admin_password",
        )

        # Create request with authenticated superuser
        request = self.factory.get("/")
        request.user = superuser

        request.user._is_authenticated = True
        self.assertTrue(request.user.is_authenticated)
        # is_superuser is True for superuser

        # Setup session without wordpress_logged_in flag
        middleware = SessionMiddleware(get_response=self.get_response_mock)
        middleware.process_request(request)
        # Intentionally not setting request.session["wordpress_logged_in"]
        request.session.save()

        # Call middleware
        response = self.middleware(request)

        # Assert logout was NOT called for superuser
        self.mock_logout.assert_not_called()

        # Assert wordpress_logged_in flag was not set
        self.assertNotIn("wordpress_logged_in", request.session)

        # Assert get_response was called with the request
        self.get_response_mock.assert_called_once_with(request)

        # Assert the response is the expected one
        self.assertEqual(response, "response")
