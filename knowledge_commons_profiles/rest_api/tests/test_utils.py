import unittest
from unittest.mock import Mock
from unittest.mock import patch

import requests
from django.test import TestCase
from django.test import override_settings

# Assuming your functions are in knowledge_commons_profiles.rest_api.utils
from knowledge_commons_profiles.rest_api.utils import build_metadata
from knowledge_commons_profiles.rest_api.utils import get_first_name
from knowledge_commons_profiles.rest_api.utils import get_last_name
from knowledge_commons_profiles.rest_api.utils import logout_all_endpoints_sync


class TestBuildMetadata(TestCase):
    def test_build_metadata_authorized_true_no_error(self):
        """Test metadata with authorized=True and no error."""
        result = build_metadata(authed=True)

        expected = {
            "meta": {
                "authorized": True,
            }
        }
        self.assertEqual(result, expected)

    def test_build_metadata_authorized_false_no_error(self):
        """Test metadata with authorized=False and no error."""
        result = build_metadata(authed=False)

        expected = {
            "meta": {
                "authorized": False,
            }
        }
        self.assertEqual(result, expected)

    def test_build_metadata_authorized_true_with_error(self):
        """Test metadata with authorized=True and error message."""
        error_msg = "Something went wrong"
        result = build_metadata(authed=True, error=error_msg)

        expected = {
            "meta": {"authorized": True, "error": "Something went wrong"}
        }
        self.assertEqual(result, expected)

    def test_build_metadata_authorized_false_with_error(self):
        """Test metadata with authorized=False and error message."""
        error_msg = "Authentication failed"
        result = build_metadata(authed=False, error=error_msg)

        expected = {
            "meta": {"authorized": False, "error": "Authentication failed"}
        }
        self.assertEqual(result, expected)

    def test_build_metadata_with_empty_error(self):
        """Test metadata with empty string error."""
        result = build_metadata(authed=True, error="")

        expected = {
            "meta": {
                "authorized": True,
            }
        }
        self.assertEqual(result, expected)

    def test_build_metadata_with_none_error_explicit(self):
        """Test metadata with explicitly passed None error."""
        result = build_metadata(authed=True, error=None)

        expected = {
            "meta": {
                "authorized": True,
            }
        }
        self.assertEqual(result, expected)
        self.assertNotIn("error", result["meta"])

    def test_build_metadata_return_type(self):
        """Test that function returns a dictionary with correct structure."""
        result = build_metadata(authed=True)

        self.assertIsInstance(result, dict)
        self.assertIn("meta", result)
        self.assertIsInstance(result["meta"], dict)
        self.assertIn("authorized", result["meta"])


class TestGetFirstName(TestCase):
    def setUp(self):
        self.mock_logger = Mock()

    def test_get_first_name_simple_name(self):
        """Test extracting first name from simple 'First Last' format."""
        profile = Mock()
        profile.name = "John Smith"
        profile.username = "jsmith"

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "John")
        self.mock_logger.warning.assert_not_called()

    def test_get_first_name_with_middle_name(self):
        """Test extracting first name with middle name included."""
        profile = Mock()
        profile.name = "John Michael Smith"
        profile.username = "jsmith"

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "John Michael")
        self.mock_logger.warning.assert_not_called()

    def test_get_first_name_single_name(self):
        """Test extracting first name when only one name provided."""
        profile = Mock()
        profile.name = "John"
        profile.username = "john"

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "John")
        self.mock_logger.warning.assert_not_called()

    def test_get_first_name_empty_name(self):
        """Test handling of empty name field."""
        profile = Mock()
        profile.name = ""
        profile.username = "user"

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_not_called()

    def test_get_first_name_none_name(self):
        """Test handling of None name field."""
        profile = Mock()
        profile.name = None
        profile.username = "user"

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_not_called()

    def test_get_first_name_whitespace_only(self):
        """Test handling of whitespace-only name."""
        profile = Mock()
        profile.name = "   "
        profile.username = "user"

        with patch(
            "knowledge_commons_profiles.rest_api.utils.HumanName"
        ) as mock_human_name:
            mock_name = Mock()
            mock_name.first = ""
            mock_name.middle = ""
            mock_human_name.return_value = mock_name

            result = get_first_name(profile, self.mock_logger)

            self.assertEqual(result, "")

    @patch("knowledge_commons_profiles.rest_api.utils.HumanName")
    def test_get_first_name_humanname_exception(self, mock_human_name):
        """Test handling of HumanName parsing exception."""
        profile = Mock()
        profile.name = "Invalid@Name#Format"
        profile.username = "user123"

        mock_human_name.side_effect = ValueError("Invalid name format")

        result = get_first_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_called_once()
        warning_call = self.mock_logger.warning.call_args[0][0]
        self.assertIn("Invalid name format", warning_call)

    def test_get_first_name_complex_name_with_prefixes(self):
        """Test handling of complex names with prefixes/suffixes."""
        profile = Mock()
        profile.name = "Dr. John Michael Smith Jr."
        profile.username = "drsmith"

        result = get_first_name(profile, self.mock_logger)

        # Should extract just the first and middle names
        self.assertIn("John", result)
        self.assertIn("Michael", result)

    def test_get_first_name_only_middle_name(self):
        """Test when HumanName returns empty first but has middle."""
        profile = Mock()
        profile.name = "Middle Name"
        profile.username = "user"

        with patch(
            "knowledge_commons_profiles.rest_api.utils.HumanName"
        ) as mock_human_name:
            mock_name = Mock()
            mock_name.first = ""
            mock_name.middle = "Middle"
            mock_human_name.return_value = mock_name

            result = get_first_name(profile, self.mock_logger)

            self.assertEqual(result, "Middle")


class TestGetLastName(TestCase):
    def setUp(self):
        self.mock_logger = Mock()

    def test_get_last_name_simple_name(self):
        """Test extracting last name from simple 'First Last' format."""
        profile = Mock()
        profile.name = "John Smith"
        profile.username = "jsmith"

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "Smith")
        self.mock_logger.warning.assert_not_called()

    def test_get_last_name_with_middle_name(self):
        """Test extracting last name from 'First Middle Last' format."""
        profile = Mock()
        profile.name = "John Michael Smith"
        profile.username = "jsmith"

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "Smith")
        self.mock_logger.warning.assert_not_called()

    def test_get_last_name_single_name(self):
        """Test extracting last name when only one name provided."""
        profile = Mock()
        profile.name = "John"
        profile.username = "john"

        with patch(
            "knowledge_commons_profiles.rest_api.utils.HumanName"
        ) as mock_human_name:
            mock_name = Mock()
            mock_name.last = ""
            mock_human_name.return_value = mock_name

            result = get_last_name(profile, self.mock_logger)

            self.assertEqual(result, "")

    def test_get_last_name_empty_name(self):
        """Test handling of empty name field."""
        profile = Mock()
        profile.name = ""
        profile.username = "user"

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_not_called()

    def test_get_last_name_none_name(self):
        """Test handling of None name field."""
        profile = Mock()
        profile.name = None
        profile.username = "user"

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_not_called()

    def test_get_last_name_none_last_from_humanname(self):
        """Test handling when HumanName returns None for last name."""
        profile = Mock()
        profile.name = "John"
        profile.username = "john"

        with patch(
            "knowledge_commons_profiles.rest_api.utils.HumanName"
        ) as mock_human_name:
            mock_name = Mock()
            mock_name.last = None
            mock_human_name.return_value = mock_name

            result = get_last_name(profile, self.mock_logger)

            self.assertEqual(result, "")

    @patch("knowledge_commons_profiles.rest_api.utils.HumanName")
    def test_get_last_name_humanname_exception(self, mock_human_name):
        """Test handling of HumanName parsing exception."""
        profile = Mock()
        profile.name = "Invalid@Name#Format"
        profile.username = "user456"

        mock_human_name.side_effect = RuntimeError("Parsing failed")

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "")
        self.mock_logger.warning.assert_called_once()
        warning_call = self.mock_logger.warning.call_args[0][0]
        self.assertIn("Parsing failed", warning_call)

    def test_get_last_name_complex_name_with_suffixes(self):
        """Test handling of complex names with suffixes."""
        profile = Mock()
        profile.name = "Dr. John Michael Smith Jr."
        profile.username = "drsmith"

        result = get_last_name(profile, self.mock_logger)

        # Should extract the surname properly
        self.assertEqual(result, "Smith")

    def test_get_last_name_hyphenated_surname(self):
        """Test handling of hyphenated surnames."""
        profile = Mock()
        profile.name = "John Smith-Jones"
        profile.username = "jsmithjones"

        result = get_last_name(profile, self.mock_logger)

        self.assertEqual(result, "Smith-Jones")

    def test_get_last_name_return_type(self):
        """Test that function always returns a string."""
        profile = Mock()
        profile.name = "John Smith"
        profile.username = "jsmith"

        result = get_last_name(profile, self.mock_logger)

        self.assertIsInstance(result, str)


class TestLogoutAllEndpointsSync(TestCase):
    @override_settings(LOGOUT_ENDPOINTS=[], STATIC_API_BEARER="test-token")
    def test_empty_endpoints_list(self):
        """Test function returns empty list when no endpoints configured."""
        result = logout_all_endpoints_sync()
        self.assertEqual(result, [])

    @override_settings(STATIC_API_BEARER="test-token")
    def test_missing_logout_endpoints_setting(self):
        """Test function handles missing LOGOUT_ENDPOINTS setting."""
        with patch("django.conf.settings") as mock_settings:
            # Remove LOGOUT_ENDPOINTS attribute
            mock_settings.STATIC_API_BEARER = "test-token"
            del mock_settings.LOGOUT_ENDPOINTS

            result = logout_all_endpoints_sync()
            self.assertEqual(result, [])

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_single_successful_request(self, mock_post):
        """Test successful logout to single endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["endpoint"], "https://api1.com/logout")
        self.assertEqual(result[0]["status"], 200)
        self.assertTrue(result[0]["success"])
        self.assertNotIn("error", result[0])

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_single_failed_request_4xx(self, mock_post):
        """Test failed logout with 4xx status code."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["endpoint"], "https://api1.com/logout")
        self.assertEqual(result[0]["status"], 401)
        self.assertFalse(result[0]["success"])
        self.assertNotIn("error", result[0])

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_single_failed_request_5xx(self, mock_post):
        """Test failed logout with 5xx status code."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["endpoint"], "https://api1.com/logout")
        self.assertEqual(result[0]["status"], 500)
        self.assertFalse(result[0]["success"])

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_request_exception(self, mock_post):
        """Test handling of network/connection exceptions."""
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["endpoint"], "https://api1.com/logout")
        self.assertIsNone(result[0]["status"])
        self.assertFalse(result[0]["success"])
        self.assertIn("error", result[0])
        self.assertIn("Connection failed", result[0]["error"])

    @override_settings(
        LOGOUT_ENDPOINTS=[
            "https://api1.com/logout",
            "https://api2.com/logout",
            "https://api3.com/logout",
        ],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_multiple_successful_requests(self, mock_post):
        """Test successful logout to multiple endpoints."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 3)
        endpoints = {r["endpoint"] for r in result}
        expected_endpoints = {
            "https://api1.com/logout",
            "https://api2.com/logout",
            "https://api3.com/logout",
        }
        self.assertEqual(endpoints, expected_endpoints)

        for r in result:
            self.assertEqual(r["status"], 200)
            self.assertTrue(r["success"])

    @override_settings(
        LOGOUT_ENDPOINTS=[
            "https://good-api.com/logout",
            "https://bad-api.com/logout",
            "https://error-api.com/logout",
        ],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_mixed_success_failure_results(self, mock_post):
        """Test mixed results with some successes and failures."""

        def side_effect(url, **kwargs):
            if "good-api" in url:
                response = Mock()
                response.status_code = 200
                return response
            if "bad-api" in url:
                response = Mock()
                response.status_code = 404
                return response
            # error-api
            message = "Request timeout"
            raise requests.Timeout(message)

        mock_post.side_effect = side_effect

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 3)

        # Check we have one of each result type
        success_count = sum(1 for r in result if r["success"])
        failure_count = sum(1 for r in result if not r["success"])
        error_count = sum(1 for r in result if "error" in r)

        self.assertEqual(success_count, 1)
        self.assertEqual(failure_count, 2)
        self.assertEqual(error_count, 1)

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_correct_headers_sent(self, mock_post):
        """Test that correct headers are sent with requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        logout_all_endpoints_sync()

        mock_post.assert_called_once_with(
            "https://api1.com/logout",
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
            json={},
            timeout=30,
        )

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"]
        * 15,  # 15 identical endpoints
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_many_endpoints_processed(self, mock_post):
        """Test that function can handle many endpoints."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertEqual(len(result), 15)
        self.assertEqual(mock_post.call_count, 15)

        for r in result:
            self.assertTrue(r["success"])
            self.assertEqual(r["status"], 200)

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="test-token",
    )
    @patch("requests.post")
    def test_return_value_structure(self, mock_post):
        """Test that return values have correct structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = logout_all_endpoints_sync()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

        item = result[0]
        self.assertIsInstance(item, dict)
        self.assertIn("endpoint", item)
        self.assertIn("status", item)
        self.assertIn("success", item)
        self.assertIsInstance(item["success"], bool)

    @override_settings(
        LOGOUT_ENDPOINTS=["https://api1.com/logout"],
        STATIC_API_BEARER="different-token",
    )
    @patch("requests.post")
    def test_uses_configured_bearer_token(self, mock_post):
        """Test that function uses the configured bearer token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        logout_all_endpoints_sync()

        called_headers = mock_post.call_args[1]["headers"]
        self.assertEqual(
            called_headers["Authorization"], "Bearer different-token"
        )


if __name__ == "__main__":
    unittest.main()
