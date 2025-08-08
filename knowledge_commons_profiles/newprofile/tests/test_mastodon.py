import datetime
from unittest import mock

import requests
from django.test import TestCase

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.mastodon import MastodonFeed


class MastodonFeedTests(TestCase):
    """Tests for the MastodonFeed class."""

    def setUp(self):
        """Set up test data and mocks."""
        # Create a MastodonFeed instance
        self.username = "testuser"
        self.server = "mastodon.social"
        self.mastodon_feed = MastodonFeed(self.username, self.server)

        # Mock cache
        self.cache_get_patcher = mock.patch("django.core.cache.cache.get")
        self.mock_cache_get = self.cache_get_patcher.start()
        self.mock_cache_get.return_value = None  # Default to cache miss

        self.cache_set_patcher = mock.patch("django.core.cache.cache.set")
        self.mock_cache_set = self.cache_set_patcher.start()

        # Mock requests.get
        self.requests_get_patcher = mock.patch("requests.get")
        self.mock_requests_get = self.requests_get_patcher.start()

        # Set up a mock response
        self.mock_response = mock.MagicMock()
        self.mock_response.raise_for_status = mock.MagicMock()
        self.mock_requests_get.return_value = self.mock_response

        # Mock logger
        self.logger_patcher = mock.patch(
            "knowledge_commons_profiles.newprofile.mastodon.logger"
        )
        self.mock_logger = self.logger_patcher.start()

    def tearDown(self):
        """Clean up after the tests."""
        self.cache_get_patcher.stop()
        self.cache_set_patcher.stop()
        self.requests_get_patcher.stop()
        self.logger_patcher.stop()

    def test_initialization(self):
        """Test that MastodonFeed initializes with correct values."""
        self.assertEqual(self.mastodon_feed.username, "testuser")
        self.assertEqual(self.mastodon_feed.server, "mastodon.social")
        self.assertEqual(
            self.mastodon_feed.api_url, "https://mastodon.social/@testuser.rss"
        )
        self.assertEqual(self.mastodon_feed.timeout, 10)
        self.assertEqual(self.mastodon_feed.max_posts, 4)
        self.assertEqual(self.mastodon_feed.cache_time, 1800)

    def test_latest_posts_cached(self):
        """Test that latest_posts returns cached posts when available."""
        # Set up mock to return cached posts
        cached_posts = [
            {
                "id": "post1",
                "url": "https://mastodon.social/@testuser/1",
                "content": "Test post 1",
                "created_at": datetime.datetime.now(tz=datetime.UTC),
                "reblogs_count": 0,
                "favourites_count": 0,
                "reblogged": False,
            }
        ]
        self.mock_cache_get.return_value = cached_posts

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that cache.get was called with the correct key
        self.mock_cache_get.assert_called_once_with(
            f"{self.username}_{self.server}_latest_posts",
            version=VERSION,
        )

        # Assert that _fetch_and_parse_posts was not called
        self.mock_requests_get.assert_not_called()

        # Assert the result is the cached posts
        self.assertEqual(result, cached_posts)

    def test_latest_posts_fetch(self):
        """Test that latest_posts fetches and parses posts when not cached."""
        # Prepare XML response
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:webfeeds="http://webfeeds.org/rss/1.0"
xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Kathleen Fitzpatrick</title>
    <description>Public posts from @kfitz@hcommons.social</description>
    <link>https://hcommons.social/@kfitz</link>
    <image>
      <url>some_url.png</url>
      <title>Kathleen Fitzpatrick</title>
      <link>https://hcommons.social/@kfitz</link>
    </image>
    <lastBuildDate>Tue, 11 Mar 2025 11:22:29 +0000</lastBuildDate>
    <generator>Mastodon v4.2.10+hometown-1.1.1</generator>
    <item>
      <guid isPermaLink="true">GUID 1</guid>
      <link>https://hcommons.social/@kfitz/114143536707391629</link>
      <pubDate>Tue, 11 Mar 2025 11:22:29 +0000</pubDate>
      <description>Some Text 1</description>
    </item>
    <item>
      <guid isPermaLink="true">GUID 2</guid>
      <link>https://hcommons.social/@kfitz/114129316780875764</link>
      <pubDate>Sat, 08 Mar 2025 23:06:10 +0000</pubDate>
      <description>Some Text 2</description>
    </item>
  </channel>
</rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that requests.get was called with the correct URL and timeout
        self.mock_requests_get.assert_called_once_with(
            self.mastodon_feed.api_url, timeout=self.mastodon_feed.timeout
        )

        # Assert that raise_for_status was called
        self.mock_response.raise_for_status.assert_called_once()

        # Assert that cache.set was called with the correct parameters
        self.mock_cache_set.assert_called_once()
        self.assertEqual(
            self.mock_cache_set.call_args[0][0],
            f"{self.username}_{self.server}_latest_posts",
        )
        self.assertEqual(
            self.mock_cache_set.call_args[0][2], self.mastodon_feed.cache_time
        )
        self.assertEqual(self.mock_cache_set.call_args[1]["version"], VERSION)

        # Verify the parsed posts
        self.assertEqual(len(result), 2)

        self.assertEqual(result[0]["id"], "GUID 1")
        self.assertEqual(
            result[0]["url"],
            "https://hcommons.social/@kfitz/114143536707391629",
        )

        self.assertEqual(result[0]["content"], "Some Text 1")
        self.assertEqual(result[0]["created_at"].year, 2025)
        self.assertEqual(result[0]["created_at"].month, 3)
        self.assertEqual(result[0]["created_at"].day, 11)
        self.assertEqual(result[0]["created_at"].hour, 11)

        self.assertEqual(result[1]["id"], "GUID 2")
        self.assertEqual(
            result[1]["url"],
            "https://hcommons.social/@kfitz/114129316780875764",
        )

        self.assertEqual(result[1]["content"], "Some Text 2")
        self.assertEqual(result[1]["created_at"].year, 2025)
        self.assertEqual(result[1]["created_at"].month, 3)
        self.assertEqual(result[1]["created_at"].day, 8)
        self.assertEqual(result[1]["created_at"].hour, 23)

    def test_fetch_request_exception(self):
        """Test error handling when the request fails."""
        # Set up mock to raise exception
        self.mock_requests_get.side_effect = (
            requests.exceptions.RequestException("Connection error")
        )

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that logger.exception was called
        self.mock_logger.exception.assert_called_once_with(
            "Error fetching %s", self.mastodon_feed.api_url
        )

        # Assert the result is an empty list
        self.assertEqual(result, [])

        # Assert cache was not set
        self.mock_cache_set.assert_not_called()

    def test_fetch_xml_parsing_error(self):
        """Test error handling when XML parsing fails."""
        # Set up mock response with invalid XML
        self.mock_response.content = b"This is not valid XML"

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that logger.exception was called
        self.mock_logger.exception.assert_called_once_with(
            "Error parsing XML from %s", self.mastodon_feed.api_url
        )

        # Assert the result is an empty list
        self.assertEqual(result, [])

        # Assert cache was not set
        self.mock_cache_set.assert_not_called()

    def test_max_posts_limit(self):
        """Test that only the maximum number of posts is returned."""
        # Prepare XML response with more posts than the limit
        xml_content = """
        <rss version="2.0">
          <channel>
            <title>Mastodon Feed</title>
            <item>
              <guid>https://mastodon.social/@testuser/1</guid>
              <link>https://mastodon.social/@testuser/1</link>
              <description><p>Test post 1</p></description>
              <pubDate>Mon, 01 Jan 2023 12:00:00 +0000</pubDate>
            </item>
            <item>
              <guid>https://mastodon.social/@testuser/2</guid>
              <link>https://mastodon.social/@testuser/2</link>
              <description><p>Test post 2</p></description>
              <pubDate>Mon, 01 Jan 2023 11:00:00 +0000</pubDate>
            </item>
            <item>
              <guid>https://mastodon.social/@testuser/3</guid>
              <link>https://mastodon.social/@testuser/3</link>
              <description><p>Test post 3</p></description>
              <pubDate>Mon, 01 Jan 2023 10:00:00 +0000</pubDate>
            </item>
            <item>
              <guid>https://mastodon.social/@testuser/4</guid>
              <link>https://mastodon.social/@testuser/4</link>
              <description><p>Test post 4</p></description>
              <pubDate>Mon, 01 Jan 2023 09:00:00 +0000</pubDate>
            </item>
            <item>
              <guid>https://mastodon.social/@testuser/5</guid>
              <link>https://mastodon.social/@testuser/5</link>
              <description><p>Test post 5</p></description>
              <pubDate>Mon, 01 Jan 2023 08:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that only max_posts (4) posts are returned
        self.assertEqual(len(result), 4)
        self.assertEqual(
            result[0]["id"], "https://mastodon.social/@testuser/1"
        )
        self.assertEqual(
            result[3]["id"], "https://mastodon.social/@testuser/4"
        )

    def test_parse_post_error_handling(self):
        """Test that errors in parsing individual posts are handled properly."""
        # Prepare XML response with one valid and one invalid post
        xml_content = """
        <rss version="2.0">
          <channel>
            <title>Mastodon Feed</title>
            <item>
              <guid>https://mastodon.social/@testuser/1</guid>
              <link>https://mastodon.social/@testuser/1</link>
              <description><p>Test post 1</p></description>
              <pubDate>Mon, 01 Jan 2023 12:00:00 +0000</pubDate>
            </item>
            <item>
              <!-- Missing required guid element -->
              <link>https://mastodon.social/@testuser/2</link>
              <description><p>Test post 2</p></description>
              <pubDate>Mon, 01 Jan 2023 11:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that only the valid post is returned
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["id"], "https://mastodon.social/@testuser/1"
        )

        # Assert that logger.warning was called for the invalid post
        self.mock_logger.warning.assert_called_once_with(
            "Missing required attribute in post: %s",
            mock.ANY,  # The AttributeError
        )

    def test_parse_post_date_error(self):
        """Test handling of invalid date formats in posts."""
        # Prepare XML response with invalid date
        xml_content = """
        <rss version="2.0">
          <channel>
            <title>Mastodon Feed</title>
            <item>
              <guid>https://mastodon.social/@testuser/1</guid>
              <link>https://mastodon.social/@testuser/1</link>
              <description><p>Test post 1</p></description>
              <pubDate>Invalid Date Format</pubDate>
            </item>
          </channel>
        </rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that the post is returned with created_at as None
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["id"], "https://mastodon.social/@testuser/1"
        )
        self.assertIsNone(result[0]["created_at"])

        # Assert that logger.warning was called for the date parsing error
        self.mock_logger.warning.assert_called_once_with(
            "Error parsing date: %s", mock.ANY  # The ValueError
        )

    def test_parse_post_missing_description(self):
        """Test handling of posts with missing description."""
        # Prepare XML response with missing description
        xml_content = """
        <rss version="2.0">
          <channel>
            <title>Mastodon Feed</title>
            <item>
              <guid>https://mastodon.social/@testuser/1</guid>
              <link>https://mastodon.social/@testuser/1</link>
              <!-- No description element -->
              <pubDate>Mon, 01 Jan 2023 12:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method
        result = self.mastodon_feed.latest_posts()

        # Assert that the post is returned with empty content
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["id"], "https://mastodon.social/@testuser/1"
        )
        self.assertEqual(result[0]["content"], "")

    def test_fetch_posts_general_exception(self):
        """Test handling of unexpected exceptions during post processing."""
        # Prepare XML response
        xml_content = """
        <rss version="2.0">
          <channel>
            <title>Mastodon Feed</title>
            <item>
              <guid>https://mastodon.social/@testuser/1</guid>
              <link>https://mastodon.social/@testuser/1</link>
              <description><p>Test post 1</p></description>
              <pubDate>Mon, 01 Jan 2023 12:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Mock _parse_post to raise an unexpected exception
        with mock.patch.object(
            MastodonFeed,
            "_parse_post",
            side_effect=Exception("Unexpected error"),
        ):
            # Call the method
            result = self.mastodon_feed.latest_posts()

            # Assert that logger.exception was called
            self.mock_logger.exception.assert_called_once_with(
                "Error processing post from %s", self.mastodon_feed.api_url
            )

            # Assert the result is an empty list
            self.assertEqual(result, [])

    def test_latest_posts_nocache_bypass(self):
        """Test that latest_posts bypasses cache when nocache=True."""
        # Set up cached posts
        cached_posts = [
            {
                "id": "cached_post",
                "url": "https://mastodon.social/@testuser/cached",
                "content": "Cached post",
                "created_at": datetime.datetime.now(tz=datetime.UTC),
                "reblogs_count": 0,
                "favourites_count": 0,
                "reblogged": False,
            }
        ]
        self.mock_cache_get.return_value = cached_posts

        # Prepare XML response for fresh fetch
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:webfeeds="http://webfeeds.org/rss/1.0"
xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Test User</title>
    <description>Public posts from @testuser@mastodon.social</description>
    <link>https://mastodon.social/@testuser</link>
    <lastBuildDate>Tue, 11 Mar 2025 11:22:29 +0000</lastBuildDate>
    <generator>Mastodon v4.2.10</generator>
    <item>
      <guid isPermaLink="true">fresh_post_guid</guid>
      <link>https://mastodon.social/@testuser/fresh</link>
      <pubDate>Tue, 11 Mar 2025 11:22:29 +0000</pubDate>
      <description>Fresh post content</description>
    </item>
  </channel>
</rss>
        """
        self.mock_response.content = xml_content.encode("utf-8")

        # Call the method with nocache=True
        result = self.mastodon_feed.latest_posts(nocache=True)

        # Assert that cache.get was NOT called (cache bypassed)
        self.mock_cache_get.assert_not_called()

        # Assert that requests.get was called (fresh fetch)
        self.mock_requests_get.assert_called_once_with(
            self.mastodon_feed.api_url, timeout=self.mastodon_feed.timeout
        )

        # Assert that cache.set was called to cache the fresh results
        self.mock_cache_set.assert_called_once()
        self.assertEqual(
            self.mock_cache_set.call_args[0][0],
            f"{self.username}_{self.server}_latest_posts",
        )

        # Verify the fresh post was returned (not cached post)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "fresh_post_guid")
        self.assertEqual(result[0]["content"], "Fresh post content")
