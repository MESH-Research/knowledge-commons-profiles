"""
Shared fakes for the UP Salesforce tests: an in-memory stand-in for
``requests.Session`` so nothing touches the network.
"""

from __future__ import annotations

import json
from typing import Any

import requests

TOKEN_URL = "https://example.my.salesforce.com/services/oauth2/token"
INSTANCE_URL = "https://example-instance.my.salesforce.com"
TOKEN_BODY = {
    "access_token": "00Dxx0000001gPz!AQEAQabcdefghijklmnopqrstuvwxyz0123456789",
    "signature": "sig",
    "scope": "api",
    "instance_url": INSTANCE_URL,
    "id": "https://login.salesforce.com/id/00Dxx/005xx",
    "token_type": "Bearer",
    "issued_at": "1730000000000",
}


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
        text: str | None = None,
    ):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text if text is not None else json.dumps(json_data or {})
        self.content = self.text.encode()

    @property
    def ok(self) -> bool:
        return self.status_code < 400  # noqa: PLR2004

    def json(self):
        if self._json is None:
            message = "no json"
            raise json.JSONDecodeError(message, self.text, 0)
        return self._json

    def raise_for_status(self):
        if not self.ok:
            message = f"{self.status_code} error"
            raise requests.HTTPError(message, response=self)


class FakeSession:
    """
    Routes requests to canned responses. ``routes`` maps
    ``(METHOD, url)`` to a FakeResponse or a list of FakeResponses that
    are consumed in order (the last one repeats).
    """

    def __init__(self, routes: dict[tuple[str, str], Any] | None = None):
        self.routes = dict(routes or {})
        self.calls: list[dict[str, Any]] = []

    def add(self, method: str, url: str, *responses: FakeResponse):
        self.routes[(method.upper(), url)] = list(responses)

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method.upper(), "url": url, **kwargs})
        key = (method.upper(), url)
        if key not in self.routes:
            msg = f"Unexpected request {method} {url}"
            raise AssertionError(msg)
        value = self.routes[key]
        if isinstance(value, list):
            response = value.pop(0) if len(value) > 1 else value[0]
        else:
            response = value
        return response

    def calls_to(self, url: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["url"] == url]

    def mount(self, *args, **kwargs):  # pragma: no cover - API parity
        pass
