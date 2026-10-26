"""
OAuth 2.0 client-credentials token acquisition for the UP External Client
App.

Salesforce External Client Apps issue tokens to a confidential client with
``grant_type=client_credentials``; the call runs as the "Run As" user
configured on the app's policies. The response carries ``access_token``
and ``instance_url`` but no refresh token and no ``expires_in``, so the
token is cached for a bounded period and the REST client re-authenticates
when Salesforce answers 401.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceAuthError,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceConfigurationError,
)
from knowledge_commons_profiles.up_salesforce.schemas import TokenResponse

logger = logging.getLogger(__name__)

TOKEN_PATH = "/services/oauth2/token"
TOKEN_CACHE_KEY = "up_salesforce_eca_access_token"
REQUEST_TIMEOUT = 30


class ClientCredentialsTokenProvider:
    """
    Obtain and cache a Salesforce access token with the client-credentials
    grant. Rotating the secret only requires changing the environment.
    """

    def __init__(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        login_url: str | None = None,
        cache_timeout: int | None = None,
        session: requests.Session | None = None,
    ):
        self.consumer_key = (
            consumer_key
            if consumer_key is not None
            else settings.UP_ECA_CONSUMER_KEY
        )
        self.consumer_secret = (
            consumer_secret
            if consumer_secret is not None
            else settings.UP_ECA_CONSUMER_SECRET
        )
        self.login_url = (
            login_url if login_url is not None else settings.UP_ECA_LOGIN_URL
        )
        self.cache_timeout = (
            cache_timeout
            if cache_timeout is not None
            else settings.UP_ECA_TOKEN_CACHE_TIMEOUT
        )
        self.session = session or requests.Session()

    @property
    def token_url(self) -> str:
        return self.login_url.rstrip("/") + TOKEN_PATH

    def _check_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("UP_ECA_CONSUMER_KEY", self.consumer_key),
                ("UP_ECA_CONSUMER_SECRET", self.consumer_secret),
                ("UP_ECA_LOGIN_URL", self.login_url),
            )
            if not value
        ]
        if missing:
            message = (
                "UP Salesforce External Client App is not configured; "
                "set " + ", ".join(missing)
            )
            raise UPSalesforceConfigurationError(message)

    def fetch_token(self) -> TokenResponse:
        """Request a brand-new token from Salesforce (no caching)."""
        self._check_configuration()

        try:
            response = self.session.request(
                "POST",
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.consumer_key,
                    "client_secret": self.consumer_secret,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            message = f"Could not reach Salesforce token endpoint: {exc}"
            logger.exception(message)
            raise UPSalesforceAuthError(message) from exc

        if not response.ok:
            raise UPSalesforceAuthError(self._describe_error(response))

        try:
            return TokenResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            message = "Salesforce token response was not understood"
            logger.exception(message)
            raise UPSalesforceAuthError(message) from exc

    @staticmethod
    def _describe_error(response) -> str:
        """Turn an OAuth error response into a readable message."""
        prefix = f"Salesforce refused to issue a token ({response.status_code})"
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and body.get("error"):
            description = body.get("error_description", "")
            return f"{prefix}: {body['error']} {description}".rstrip()
        return f"{prefix}: {response.text[:200]}"

    def peek_cached(self) -> TokenResponse | None:
        """Return the cached token without contacting Salesforce."""
        raw = cache.get(TOKEN_CACHE_KEY, version=VERSION)
        if not raw:
            return None
        try:
            return TokenResponse.model_validate_json(raw)
        except ValidationError:
            self.invalidate()
            return None

    def get_token(self, *, force_refresh: bool = False) -> TokenResponse:
        """Return a cached token, fetching a new one when required."""
        if not force_refresh:
            cached = self.peek_cached()
            if cached is not None:
                return cached

        token = self.fetch_token()
        cache.set(
            TOKEN_CACHE_KEY,
            token.model_dump_json(),
            timeout=self.cache_timeout,
            version=VERSION,
        )
        return token

    def invalidate(self) -> None:
        """Drop the cached token so the next call fetches a fresh one."""
        cache.delete(TOKEN_CACHE_KEY, version=VERSION)
