"""
Middleware for profiles
"""

import logging
from enum import Enum

import sentry_sdk
from authlib.integrations.base_client import InvalidTokenError
from authlib.integrations.base_client import MissingRequestTokenError
from authlib.integrations.base_client import MissingTokenError
from authlib.integrations.base_client import OAuthError
from authlib.integrations.base_client import UnsupportedTokenTypeError
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,  # DNS failure,
    # refused connection, etc.
)
from requests.exceptions import (
    HTTPError,  # if you call response.raise_for_status()
)
from requests.exceptions import (
    RequestException,  # the base class for all requests exceptions
)
from requests.exceptions import (
    Timeout,  # when your timeout parameter is exceeded
)

from knowledge_commons_profiles.cilogon.oauth import oauth

logger = logging.getLogger(__name__)

User = get_user_model()


class RetryStatus(Enum):
    """
    Enumeration for retry status
    """

    FIRST = 1
    SECOND = 2
    FINAL = 3

    def successor(self):
        """
        Go to the next RetryStatus
        """
        new_value = self.value + 1
        if new_value > RetryStatus.FINAL.value:
            error_message = "Enumeration ended"
            raise ValueError(error_message)
        return RetryStatus(new_value)

    def predecessor(self):
        """
        Go to the previous RetryStatus
        """
        new_value = self.value - 1
        if new_value == 0:
            error_message = "Enumeration ended"
            raise ValueError(error_message)
        return RetryStatus(new_value)


class AutoRefreshTokenMiddleware(MiddlewareMixin):
    def process_request(
        self, request, current_attempt: RetryStatus = RetryStatus.FIRST
    ):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        # Grab the stored token
        token = request.session.get("oidc_token")
        if not token:
            return

        # Create an Authlib client and set its token
        client = oauth.create_client("cilogon")
        client.token = token

        try:
            # This GET will trigger a refresh if needed,
            # via the token_endpoint metadata
            client.get(client.server_metadata["userinfo_endpoint"])
        except (
            MissingTokenError,
            InvalidTokenError,
            MissingRequestTokenError,
        ):
            # e.g. refresh_token expired or invalid
            # log the user out and force re-auth
            # TODO: logout
            logging.info("Token invalid or expired")
        except (UnsupportedTokenTypeError, OAuthError) as e:
            # log to Sentry
            # log the user out
            # TODO: logout
            logging.info("Token error: %s", e.description)
            sentry_sdk.capture_exception(e)
        except (RequestsConnectionError, Timeout, RequestException, HTTPError):
            # transient network error
            logging.info("Transient network error in auth")

            if current_attempt == RetryStatus.FINAL:
                # log the user out
                # TODO: logout
                pass
            else:
                self.process_request(
                    request, current_attempt=current_attempt.successor()
                )

        # Persist the possibly-updated token back
        request.session["oidc_token"] = client.token
