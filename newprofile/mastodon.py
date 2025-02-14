"""
Fetches Mastodon feed latest and handles caching
"""

from datetime import datetime

import requests

from django.core.cache import cache
from lxml import etree

import newprofile


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
        # The API endpoint to fetch the latest posts
        self.username = username
        self.server = server
        self.api_url = f"https://{self.server}/@{self.username}.rss"

    @property
    def latest_posts(self):
        """
        Fetches and parses the latests posts in the Mastodon feed.

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
            try:
                response = requests.get(self.api_url)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching {self.api_url}: {e}")
                return []

            try:
                root = etree.fromstring(response.content)
            except etree.XMLSyntaxError as e:
                print(f"Error parsing XML from {self.api_url}: {e}")
                return []

            try:
                posts = root.findall(".//item")
            except AttributeError as e:
                print(f"Error parsing XML from {self.api_url}: {e}")
                return []

            latest_posts = []
            for post in posts[0:4]:
                try:
                    guid = post.find("guid").text
                    link = post.find("link").text
                    description = post.find("description").text
                    if description:
                        description = description.replace("<p>", "").replace(
                            "</p>", ""
                        )
                    else:
                        description = ""
                    pub_date = post.find("pubDate").text
                    if pub_date:
                        try:
                            created_at = datetime.strptime(
                                pub_date, "%a, %d %b %Y %H:%M:%S %z"
                            )
                        except ValueError as e:
                            print(
                                f"Error parsing date from {self.api_url}: {e}"
                            )
                            created_at = None
                            return []
                    else:
                        created_at = None

                    latest_posts.append(
                        {
                            "id": guid,
                            "url": link,
                            "content": description,
                            "created_at": created_at,
                            "reblogs_count": 0,
                            "favourites_count": 0,
                            "reblogged": False,
                        }
                    )
                except AttributeError as e:
                    print(f"Error parsing XML from {self.api_url}: {e}")
                    return []

            cache.set(
                cache_key, latest_posts, 1800, version=newprofile.__version__
            )
        return latest_posts
