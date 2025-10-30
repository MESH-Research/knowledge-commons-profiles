from abc import ABC
from abc import abstractmethod
from functools import wraps

from django.core.cache import cache


class APIError(Exception):
    """Base exception for MLA API errors"""


def rate_limit(max_calls: int, period: int):
    """Rate limit decorator"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            cache_key = f"api_rate_limit_{func.__name__}"

            # Get current count
            current = cache.get(cache_key, 0)

            if current >= max_calls:
                message = "Rate limit exceeded"
                raise APIError(message)

            # Increment and set expiry
            cache.set(cache_key, current + 1, timeout=period)

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


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
    def search_multiple(self, emails):
        """
        Search for a user
        :param emails: the multiple emails to search for
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
