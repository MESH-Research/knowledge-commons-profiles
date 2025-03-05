"""
Fetches Mastodon feed latest and handles caching
"""

# pylint: disable=c-extension-no-member, too-few-public-methods
# pylint: disable=broad-exception-caught
import logging
from datetime import datetime

import newprofile
import requests
from django.core.cache import cache
from lxml import etree

logger = logging.getLogger(__name__)


class MastodonFeed:
    """
    Fetches Mastodon feed latest and handles caching
    """

    def __init__(self, username, server):
        """
        Initialize the MastodonFeed object.

        :param username: The username on Mastodon
        :param server: The server where the Mastodon profile is hosted
        """
        self.username = username
        self.server = server
        self.api_url = f"https://{self.server}/@{self.username}.rss"
        self.timeout = 10  # Request timeout in seconds
        self.max_posts = 4  # Maximum posts to return
        self.cache_time = 1800  # Cache time in seconds (30 minutes)

    @property
    def latest_posts(self):
        """
        Fetches and parses the latest posts in the Mastodon feed.

        This method fetches the latest posts from the Mastodon API,
        parses them and returns them in a structured format.

        Returns a list of dictionaries, each containing the following
        keys:

        - id: The id of the post
        - url: The URL of the post
        - content: The text content of the post
        - created_at: The date and time the post was created
        - reblogs_count: The number of times the post has been reblogged
        - favourites_count: The number of times the post has been favourited
        - reblogged: Whether the post is a reblog or not
        """
        cache_key = f"{self.username}_{self.server}_latest_posts"
        latest_posts = cache.get(cache_key, version=newprofile.__version__)

        if latest_posts is None:
            latest_posts = self._fetch_and_parse_posts()
            if latest_posts:
                cache.set(
                    cache_key,
                    latest_posts,
                    self.cache_time,
                    version=newprofile.__version__,
                )

        return latest_posts

    def _fetch_and_parse_posts(self):
        """
        Fetch posts from Mastodon and parse them.

        Returns:
            list: List of parsed post dictionaries
        """
        # Fetch RSS feed from Mastodon
        try:
            response = requests.get(self.api_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Error fetching %s", self.api_url)
            return []

        # Parse XML
        try:
            root = etree.fromstring(response.content)  # noqa: S320
            posts = root.findall(".//item")
        except (etree.XMLSyntaxError, AttributeError):
            logger.exception("Error parsing XML from %s", self.api_url)
            return []

        # Process posts
        latest_posts = []
        for post in posts[: self.max_posts]:
            try:
                post_data = self._parse_post(post)
                if post_data:
                    latest_posts.append(post_data)
            except Exception:
                logger.exception(
                    "Error processing post from %s",
                    self.api_url,
                )
                # Continue processing other posts
                continue

        return latest_posts

    @staticmethod
    def _parse_post(post):
        """
        Parse a single post XML element.

        Args:
            post: XML element containing post data

        Returns:
            dict: Parsed post data or None if invalid
        """
        # Extract basic info
        try:
            guid = post.find("guid").text
            link = post.find("link").text

            # Handle description
            description_elem = post.find("description")
            description = ""
            if description_elem is not None and description_elem.text:
                description = description_elem.text.replace("<p>", "").replace(
                    "</p>",
                    "",
                )

            # Parse date
            pub_date_elem = post.find("pubDate")
            created_at = None

            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    created_at = datetime.strptime(
                        pub_date_elem.text,
                        "%a, %d %b %Y %H:%M:%S %z",
                    )
                except ValueError as e:
                    logger.warning("Error parsing date: %s", e)
                    # Continue with created_at as None

            return {  # noqa: TRY300
                "id": guid,
                "url": link,
                "content": description,
                "created_at": created_at,
                "reblogs_count": 0,
                "favourites_count": 0,
                "reblogged": False,
            }

        except AttributeError as e:
            logger.warning("Missing required attribute in post: %s", e)
            return None
