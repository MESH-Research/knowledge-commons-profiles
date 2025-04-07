"""Tests for the WorksDeposits class.

This module contains tests for the WorksDeposits class, which handles
displaying a user's deposited works by fetching them from an external API.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TransactionTestCase
from django.test import override_settings

from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.newprofile.works import WorksDeposits


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
)
class WorksDepositsTest(TransactionTestCase):
    """Test suite for the WorksDeposits class."""

    def setUp(self):
        """Set up test environment before each test."""
        self.user_id = "user-12345"
        self.works_url = "https://example.org/works"
        self.works_deposits = WorksDeposits(self.user_id, self.works_url)

        # Clear cache before each test
        cache.clear()

        # Mock sample API response
        self.sample_works_response = {
            "hits": {
                "hits": [
                    {
                        "metadata": {
                            "title": "Test Article",
                            "publication_date": "2023-01-15",
                            "resource_type": {"title": {"en": "Article"}},
                        },
                        "links": {
                            "latest_html": "https://example.org/works/"
                            "test-article"
                        },
                    },
                    {
                        "metadata": {
                            "title": "Research Paper",
                            "publication_date": "2023-02-20",
                            "resource_type": {"title": {"en": "Paper"}},
                        },
                        "links": {
                            "latest_html": "https://example.org/works/"
                            "research-paper"
                        },
                    },
                    {
                        "metadata": {
                            "title": "Another Article",
                            "publication_date": "2023-03-10",
                            "resource_type": {"title": {"en": "Article"}},
                        },
                        "links": {
                            "latest_html": "https://example.org/works/"
                            "another-article"
                        },
                    },
                ]
            }
        }

    async def async_test_wrapper(self, coroutine):
        """Wrapper to run async tests."""
        return await coroutine

    @patch("knowledge_commons_profiles.newprofile.works.requests.Session")
    def test_display_filter_from_cache(self, mock_client_session):
        """Test display_filter when result is already in cache."""
        # Set up cache
        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-{self.user_id}"
        )

        cache.set(
            cache_key,
            "<div>Cached HTML</div>",
            3600,
            version=newprofile.__version__,
        )

        # Call the method
        result = self.works_deposits.display_filter()

        # Assertions
        mock_client_session.assert_not_called()  # don't create API session
        self.assertEqual(result, "<div>Cached HTML</div>")

    @patch("knowledge_commons_profiles.newprofile.works.requests.Session")
    def test_display_filter_no_works_found(self, mock_client_session):
        """Test display_filter when no works are found in the API."""
        # Set up mocks
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = MagicMock(return_value={"hits": {"hits": []}})

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "\n")

        # Cache should be set with empty string
        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-{self.user_id}"
        )
        cached_value = cache.get(cache_key, version=newprofile.__version__)
        self.assertEqual(cached_value, "\n")

    @patch("knowledge_commons_profiles.newprofile.works.requests.Session")
    def test_display_filter_malformed_response(self, mock_client_session):
        """Test display_filter with malformed API response."""
        # Set up mocks
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = MagicMock(return_value={"invalid": "response"})

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "\n")

    @patch("knowledge_commons_profiles.newprofile.works.requests.Session")
    def test_display_filter_api_error(self, mock_client_session):
        """Test display_filter when API returns an error."""
        # Set up mocks
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=requests.exceptions.RequestException
        )

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "\n")

    @patch("knowledge_commons_profiles.newprofile.works.requests.Session")
    def test_display_filter_connection_error(self, mock_client_session):
        """Test display_filter with connection error to API."""
        # Set up mocks to simulate connection error
        mock_session = MagicMock()
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get = MagicMock(
            side_effect=requests.exceptions.RequestException(
                "Connection error"
            )
        )

        # Call the method
        result = self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "\n")

    def test_works_deposits_properties(self):
        """Test the static properties of the WorksDeposits class."""
        # Check class properties
        self.assertEqual(WorksDeposits.name, "Works Deposits")
        self.assertTrue(WorksDeposits.accepts_null_value)

        # Check instance properties
        self.assertEqual(self.works_deposits.user, self.user_id)
        self.assertEqual(self.works_deposits.works_url, self.works_url)
