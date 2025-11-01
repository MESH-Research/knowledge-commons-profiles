"""
The MLA API for synchronising user data
"""

import logging

from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass

logger = logging.getLogger(__name__)


class MSU(SyncClass):
    """
    Check for MSU membership.

    The API has several methods: search (will find a record by email),
    get_user_info (will find a record by id), is_member (returns a boolean for
    whether the user is a member) and groups (returns a user's groups).
    """

    def __init__(self):
        """
        Constructor
        """
        self.search_url = "msu.edu"

    def is_member(self, user_id: str | int | list) -> bool:
        """
        Check if a user is a member
        """
        return (
            True if user_id.lower().endswith(self.search_url.lower()) else None
        )

    def search_multiple(self, emails) -> dict:
        """
        Search for a user
        :param emails: the emails to search for; first hit will be returned
        """
        for email in emails:
            try:
                if email.lower().endswith(self.search_url.lower()):
                    return {"MSU": email}

            except ValueError:
                logger.exception("Error parsing email in MSU search")
                continue

        return {"MSU": None}

    def get_sync_id(self, response):
        """
        Get a sync ID from the api response
        :param response: the response from the API
        """
        if response:
            return (
                response
                if response.lower().endswith(self.search_url.lower())
                else None
            )
        return None

    def search(self, email) -> dict:
        """
        Search for a user
        :param email: the email to search for
        """
        try:
            if email.lower().endswith(self.search_url.lower()):
                return {"MSU": email}
        except ValueError:
            logger.exception("Error parsing email in MSU search")
            return {"MSU": None}

        return {"MSU": None}

    def get_user_info(self, mla_id: str | int) -> dict:
        """
        Search for a user
        """
        raise NotImplementedError

    def groups(self, user_id: str | int | list) -> list[str]:
        """
        Get a user's groups
        """
        return []
