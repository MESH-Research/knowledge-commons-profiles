"""
Test suite for SparkPost email client module.
"""

from unittest import mock

import pytest
import requests

from knowledge_commons_profiles.cron.emails import SparkPostEmailClient

# Test constants
EXPECTED_TIMEOUT = 10


class TestSparkPostEmailClientInit:
    """Tests for SparkPostEmailClient initialization."""

    @mock.patch(
        "knowledge_commons_profiles.cron.emails.SPARKPOST_API_KEY",
        "test-key",
    )
    @mock.patch(
        "knowledge_commons_profiles.cron.emails.SPARKPOST_API_URL",
        "https://api.sparkpost.com/api/v1",
    )
    def test_client_initialization(self):
        """Test that the client initializes with correct values."""
        client = SparkPostEmailClient()

        assert client.api_key == "test-key"
        assert client.base_url == "https://api.sparkpost.com/api/v1"
        assert client.headers == {
            "Authorization": "test-key",
            "Content-Type": "application/json",
        }


class TestSendEmail:
    """Tests for the send_email method."""

    @pytest.fixture
    def client(self):
        """Create a SparkPostEmailClient with mocked credentials."""
        with (
            mock.patch(
                "knowledge_commons_profiles.cron.emails.SPARKPOST_API_KEY",
                "test-key",
            ),
            mock.patch(
                "knowledge_commons_profiles.cron.emails.SPARKPOST_API_URL",
                "https://api.sparkpost.com/api/v1",
            ),
        ):
            return SparkPostEmailClient()

    def test_send_email_with_simple_recipients(self, client):
        """Test sending email with a list of email addresses."""
        with mock.patch("requests.post") as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {"results": {"id": "12345"}}
            mock_post.return_value = mock_response

            result = client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello World</p>",
                recipients=["recipient1@example.com", "recipient2@example.com"],
            )

            # Verify the API was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check URL
            expected_url = "https://api.sparkpost.com/api/v1/transmissions"
            assert call_args[0][0] == expected_url

            # Check payload
            payload = call_args[1]["json"]
            assert payload["content"]["from"]["email"] == "sender@example.com"
            assert payload["content"]["from"]["name"] == "Sender Name"
            assert payload["content"]["subject"] == "Test Subject"
            assert payload["content"]["html"] == "<p>Hello World</p>"
            assert payload["recipients"] == [
                {"address": {"email": "recipient1@example.com"}},
                {"address": {"email": "recipient2@example.com"}},
            ]
            assert payload["options"]["open_tracking"] is True
            assert payload["options"]["click_tracking"] is True

            assert result == {"results": {"id": "12345"}}

    def test_send_email_with_recipient_objects(self, client):
        """Test sending email with advanced recipient objects."""
        with mock.patch("requests.post") as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {"results": {"id": "12345"}}
            mock_post.return_value = mock_response

            recipient_objects = [
                {
                    "address": {
                        "email": "user@example.com",
                        "name": "User Name",
                    },
                    "substitution_data": {"first_name": "User"},
                }
            ]

            result = client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                recipient_objects=recipient_objects,
            )

            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["recipients"] == recipient_objects
            assert result == {"results": {"id": "12345"}}

    def test_send_email_raises_without_recipients(self, client):
        """Test that ValueError is raised when no recipients are provided."""
        with pytest.raises(ValueError, match="recipients.*must be provided"):
            client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
            )

    def test_send_email_with_optional_fields(self, client):
        """Test sending email with all optional fields."""
        with mock.patch("requests.post") as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {"results": {"id": "12345"}}
            mock_post.return_value = mock_response

            client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                text_content="Hello plain text",
                recipients=["recipient@example.com"],
                reply_to="reply@example.com",
                tags=["newsletter", "welcome"],
                track_opens=False,
                track_clicks=False,
            )

            call_args = mock_post.call_args
            payload = call_args[1]["json"]

            assert payload["content"]["text"] == "Hello plain text"
            assert payload["content"]["reply_to"] == "reply@example.com"
            assert payload["tags"] == ["newsletter", "welcome"]
            assert payload["options"]["open_tracking"] is False
            assert payload["options"]["click_tracking"] is False

    def test_send_email_handles_request_exception(self, client):
        """Test that request exceptions are handled gracefully."""
        with mock.patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError(
                "Network error"
            )

            result = client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                recipients=["recipient@example.com"],
            )

            assert result == {"success": False, "error": "Request failed"}

    def test_send_email_handles_http_error(self, client):
        """Test that HTTP errors are handled gracefully."""
        with mock.patch("requests.post") as mock_post:
            mock_response = mock.Mock()
            mock_response.raise_for_status.side_effect = (
                requests.exceptions.HTTPError("400 Bad Request")
            )
            mock_post.return_value = mock_response

            result = client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                recipients=["recipient@example.com"],
            )

            assert result == {"success": False, "error": "Request failed"}

    def test_send_email_handles_timeout(self, client):
        """Test that timeouts are handled gracefully."""
        with mock.patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout(
                "Request timed out"
            )

            result = client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                recipients=["recipient@example.com"],
            )

            assert result == {"success": False, "error": "Request failed"}

    def test_send_email_uses_correct_timeout(self, client):
        """Test that requests are made with the correct timeout."""
        with mock.patch("requests.post") as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {}
            mock_post.return_value = mock_response

            client.send_email(
                from_email="sender@example.com",
                from_name="Sender Name",
                subject="Test Subject",
                html_content="<p>Hello</p>",
                recipients=["recipient@example.com"],
            )

            call_args = mock_post.call_args
            assert call_args[1]["timeout"] == EXPECTED_TIMEOUT
