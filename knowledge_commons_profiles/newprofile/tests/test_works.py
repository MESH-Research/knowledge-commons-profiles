"""Tests for the WorksDeposits class.

This module contains tests for the WorksDeposits class, which handles
displaying a user's deposited works by fetching them from an external API.
"""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import aiohttp
from asgiref.sync import sync_to_async
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

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    @patch("knowledge_commons_profiles.newprofile.works.render_to_string")
    async def test_display_filter_successful_api_call(
        self, mock_render, mock_client_session
    ):
        """Test display_filter with a successful API call."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=self.sample_works_response)

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        mock_render.return_value = "<div>Rendered HTML</div>"

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        expected_endpoint = (
            f"{self.works_url}/api/records?q=metadata.creators.person_or_org."
            f"identifiers.identifier:{self.user_id}&size=100"
        )

        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[0][0]
        self.assertEqual(call_args, expected_endpoint)

        # Check that render_to_string was called with correct context
        mock_render.assert_called_once()
        context = mock_render.call_args[1]["context"]
        self.assertIn("works_links", context)
        self.assertIn("Article", context["works_links"])
        self.assertIn("Paper", context["works_links"])
        self.assertEqual(len(context["works_links"]["Article"]), 2)
        self.assertEqual(len(context["works_links"]["Paper"]), 1)

        # Check that the result is the rendered HTML
        self.assertEqual(result, "<div>Rendered HTML</div>")

        # Check that the cache was set
        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-{self.user_id}"
        )
        cached_value = await sync_to_async(cache.get)(
            cache_key, version=newprofile.__version__
        )
        self.assertEqual(cached_value, "<div>Rendered HTML</div>")

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_from_cache(self, mock_client_session):
        """Test display_filter when result is already in cache."""
        # Set up cache
        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-{self.user_id}"
        )
        await sync_to_async(cache.set)(
            cache_key,
            "<div>Cached HTML</div>",
            3600,
            version=newprofile.__version__,
        )

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        mock_client_session.assert_not_called()  # don't create API session
        self.assertEqual(result, "<div>Cached HTML</div>")

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_no_works_found(self, mock_client_session):
        """Test display_filter when no works are found in the API."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"hits": {"hits": []}})

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "")

        # Cache should be set with empty string
        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-{self.user_id}"
        )
        cached_value = await sync_to_async(cache.get)(
            cache_key, version=newprofile.__version__
        )
        self.assertEqual(cached_value, None)

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_malformed_response(
        self, mock_client_session
    ):
        """Test display_filter with malformed API response."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"invalid": "response"})

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "")

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_api_error(self, mock_client_session):
        """Test display_filter when API returns an error."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientError
        )

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "")

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_connection_error(self, mock_client_session):
        """Test display_filter with connection error to API."""
        # Set up mocks to simulate connection error
        mock_session = AsyncMock()
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get = AsyncMock(
            side_effect=aiohttp.ClientError("Connection error")
        )

        # Call the method
        result = await self.works_deposits.display_filter()

        # Assertions
        self.assertEqual(result, "")

    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_correct_headers(self, mock_client_session):
        """Test that correct headers are sent with the API request."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=self.sample_works_response)

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        # Call the method
        await self.works_deposits.display_filter()

        # Assert headers are correct
        expected_headers = {
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:134.0) "
            "Gecko/20100101 Firefox/134.0",
        }

        mock_session.get.assert_called_once()
        headers_arg = mock_session.get.call_args[1].get("headers", {})
        self.assertEqual(headers_arg, expected_headers)

    @patch("knowledge_commons_profiles.newprofile.works.render_to_string")
    @patch("knowledge_commons_profiles.newprofile.works.aiohttp.ClientSession")
    async def test_display_filter_template_context(
        self, mock_client_session, mock_render
    ):
        """Test the template context passed to render_to_string."""
        # Set up mocks
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=self.sample_works_response)

        # Configure mock session
        mock_client_session.return_value = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_response
        mock_response.__aenter__.return_value = mock_response

        mock_render.return_value = "<div>Works content</div>"

        # Call the method
        await self.works_deposits.display_filter()

        # Check template and context
        mock_render.assert_called_once_with(
            "newprofile/works.html",
            context={
                "works_links": {
                    "Article": [
                        {
                            "title": "Test Article",
                            "url": "https://example.org/works/test-article",
                            "date": "2023-01-15",
                        },
                        {
                            "title": "Another Article",
                            "url": "https://example.org/works/another-article",
                            "date": "2023-03-10",
                        },
                    ],
                    "Paper": [
                        {
                            "title": "Research Paper",
                            "url": "https://example.org/works/research-paper",
                            "date": "2023-02-20",
                        }
                    ],
                }
            },
        )

    def test_works_deposits_properties(self):
        """Test the static properties of the WorksDeposits class."""
        # Check class properties
        self.assertEqual(WorksDeposits.name, "Works Deposits")
        self.assertTrue(WorksDeposits.accepts_null_value)

        # Check instance properties
        self.assertEqual(self.works_deposits.user, self.user_id)
        self.assertEqual(self.works_deposits.works_url, self.works_url)

    def test_run_async_tests(self):
        """Run all async tests."""
        test_methods = [
            self.test_display_filter_successful_api_call,
            self.test_display_filter_from_cache,
            self.test_display_filter_no_works_found,
            self.test_display_filter_malformed_response,
            self.test_display_filter_api_error,
            self.test_display_filter_connection_error,
            self.test_display_filter_correct_headers,
            self.test_display_filter_template_context,
        ]

        for method in test_methods:
            self.async_test_wrapper(method())
