from abc import ABC
from abc import abstractmethod


class SyncClass(ABC):
    """
    Abstract class for Sync APIs
    """

    @abstractmethod
    def search(self, email):
        """
        Search for a user
        :param email: the email to search for
        """

    @abstractmethod
    def get_user_info(self, user_id):
        """
        Get user info
        :param user_id: the user ID
        """

    @abstractmethod
    def is_member(self, user_id) -> bool:
        """
        Check if a user is a member
        :param user_id: the user ID
        """

    @abstractmethod
    def groups(self, user_id) -> list[str]:
        """
        Get a user's groups
        :param user_id: the user ID
        """
