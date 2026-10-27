"""
A thin Salesforce REST client authenticated with the External Client App.
"""

from __future__ import annotations

import logging
from http import HTTPMethod
from http import HTTPStatus
from typing import Any

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from knowledge_commons_profiles.up_salesforce.auth import (
    ClientCredentialsTokenProvider,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceAuthError,
)
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceError,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
USERINFO_PATH = "/services/oauth2/userinfo"
VERSIONS_PATH = "/services/data/"


def _build_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[500, 502, 503, 504],
        backoff_factor=1,
    )
    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False,
        ),
    )
    return session


class SalesforceRestClient:
    """
    Make authenticated calls against the Salesforce REST API. A 401 causes
    the cached token to be invalidated and the request retried once.
    """

    def __init__(
        self,
        token_provider: ClientCredentialsTokenProvider | None = None,
        api_version: str | None = None,
        session: requests.Session | None = None,
    ):
        self.session = session or _build_session()
        self.token_provider = token_provider or ClientCredentialsTokenProvider(
            session=self.session
        )
        self._api_version = api_version

    @property
    def api_version(self) -> str:
        """Explicit value if given, otherwise settings at use time."""
        return self._api_version or settings.UP_ECA_API_VERSION

    def build_url(self, path: str, instance_url: str) -> str:
        """
        Resolve ``path`` against the token's instance URL. A full URL is
        returned as-is, an absolute path (``/services/...``) is appended to
        the instance, and anything else is relative to the versioned data
        root (``/services/data/vNN.N/``).
        """
        if path.startswith(("http://", "https://")):
            return path
        base = instance_url.rstrip("/")
        if path.startswith("/"):
            return base + path
        return f"{base}/services/data/{self.api_version}/{path}"

    def request(
        self,
        method: HTTPMethod | str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Perform a request, re-authenticating once on a 401."""
        response = self._send(method, path, params, json)

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Salesforce returned 401; refreshing access token")
            self.token_provider.invalidate()
            response = self._send(method, path, params, json)
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                raise UPSalesforceAuthError(self._describe_error(response))

        if not response.ok:
            raise UPSalesforceError(self._describe_error(response))

        if response.status_code == HTTPStatus.NO_CONTENT or not response.text:
            return None

        try:
            return response.json()
        except ValueError as exc:
            message = "Salesforce returned a non-JSON response"
            raise UPSalesforceError(message) from exc

    def _send(self, method, path, params, json):
        token = self.token_provider.get_token()
        url = self.build_url(path, token.instance_url)
        try:
            return self.session.request(
                str(method),
                url,
                params=params,
                json=json,
                headers={
                    "Authorization": f"Bearer {token.access_token}",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            message = f"Request to Salesforce failed: {exc}"
            logger.exception(message)
            raise UPSalesforceError(message) from exc

    @staticmethod
    def _describe_error(response) -> str:
        """
        Salesforce REST errors are a list of ``{errorCode, message}``.
        """
        prefix = f"Salesforce API error ({response.status_code})"
        try:
            body = response.json()
        except ValueError:
            return f"{prefix}: {response.text[:200]}"
        if isinstance(body, list):
            parts = [
                f"{item.get('errorCode', 'UNKNOWN')}: {item.get('message', '')}"
                for item in body
                if isinstance(item, dict)
            ]
            if parts:
                return f"{prefix}: " + "; ".join(parts)
        if isinstance(body, dict) and "errorCode" in body:
            return f"{prefix}: {body['errorCode']}: {body.get('message', '')}"
        return f"{prefix}: {response.text[:200]}"

    def query(self, soql: str) -> dict[str, Any]:
        """Run a SOQL query and return the first page of results."""
        return self.request(HTTPMethod.GET, "query", params={"q": soql})

    def query_all(self, soql: str) -> list[dict[str, Any]]:
        """Run a SOQL query following ``nextRecordsUrl`` to the end."""
        page = self.query(soql)
        records = list(page.get("records", []))
        while not page.get("done", True) and page.get("nextRecordsUrl"):
            page = self.request(HTTPMethod.GET, page["nextRecordsUrl"])
            records.extend(page.get("records", []))
        return records

    def limits(self) -> dict[str, Any]:
        return self.request(HTTPMethod.GET, "limits")

    def userinfo(self) -> dict[str, Any]:
        """Identity of the user the External Client App runs as."""
        return self.request(HTTPMethod.GET, USERINFO_PATH)

    def versions(self) -> list[dict[str, Any]]:
        return self.request(HTTPMethod.GET, VERSIONS_PATH)

    def describe(self, sobject: str) -> dict[str, Any]:
        return self.request(HTTPMethod.GET, f"sobjects/{sobject}/describe")
