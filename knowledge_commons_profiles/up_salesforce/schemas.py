"""
Pydantic schemas for Salesforce responses used by the UP sync.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict

T = TypeVar("T")

MASK_EDGE = 4
MASK_MIN_LENGTH = 12


class TokenResponse(BaseModel):
    """The JSON body returned by ``/services/oauth2/token``."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    issued_at: str | None = None
    scope: str | None = None
    id: str | None = None
    signature: str | None = None

    @property
    def issued_at_datetime(self) -> datetime | None:
        """``issued_at`` is epoch milliseconds expressed as a string."""
        if not self.issued_at:
            return None
        try:
            return datetime.fromtimestamp(int(self.issued_at) / 1000, tz=UTC)
        except TypeError, ValueError:
            return None

    def masked_token(self) -> str:
        """
        A display form that never leaks the token: the first and last four
        characters with the middle elided, or all asterisks when the
        token is too short for that to be safe.
        """
        token = self.access_token
        if len(token) <= MASK_MIN_LENGTH:
            return "*" * len(token)
        return f"{token[:MASK_EDGE]}…{token[-MASK_EDGE:]}"


class SFAttributes(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    url: str | None = None


class Contact(BaseModel):
    """A Salesforce Contact record (fields used by the UP sync)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    attributes: SFAttributes | None = None
    Id: str
    Name: str | None = None
    Email: str | None = None
    AccountId: str | None = None
    Current_Staff__c: bool | None = None
    UP_Commons_Eligible__c: bool | None = None


# ruff: noqa: N815
class QueryResponse(BaseModel, Generic[T]):
    """The envelope returned by the SOQL ``query`` resource."""

    model_config = ConfigDict(extra="ignore")

    totalSize: int
    done: bool
    records: list[T]
    nextRecordsUrl: str | None = None
