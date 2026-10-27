"""
The UP sync class backed by the External Client App credentials.

It implements the same ``SyncClass`` interface as the legacy
``cilogon.sync_apis.up.UP`` so it can be dropped in later, but it is NOT
registered anywhere yet: the legacy class keeps serving production.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import sentry_sdk
from django.conf import settings
from django.core.cache import cache
from pydantic import TypeAdapter
from pydantic import ValidationError

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.common.profiles_email import normalize_email
from knowledge_commons_profiles.up_salesforce.client import SalesforceRestClient
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceError,
)
from knowledge_commons_profiles.up_salesforce.schemas import Contact
from knowledge_commons_profiles.up_salesforce.schemas import QueryResponse
from knowledge_commons_profiles.up_salesforce.soql import soql_quote

logger = logging.getLogger(__name__)

SYNC_KEY = "UP"
SEARCH_CACHE_PREFIX = "up_eca_search_"
CONTACT_FIELDS = (
    "Id",
    "Name",
    "Email",
    "AccountId",
    "Current_Staff__c",
    "UP_Commons_Eligible__c",
)
EMAIL_REGEX = re.compile(
    r"^(?P<local>[a-zA-Z0-9_.+'-]+)@(?P<domain>[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$"
)


@dataclass
class MembershipLookup:
    """A human-friendly summary of a contact lookup."""

    found: bool
    matched_email: str | None = None
    contact: Contact | None = None
    account_id: str | None = None
    eligible: bool = False


def contact_soql(email: str) -> str:
    """The SOQL used to find a Contact by (already normalised) email."""
    fields = ", ".join(CONTACT_FIELDS)
    # The only interpolated user value is passed through soql_quote, which
    # escapes the characters that could terminate the literal.
    where = f"Email = {soql_quote(email)}"
    return f"SELECT {fields} FROM Contact WHERE {where}"  # noqa: S608


class UPExternalClientApp(SyncClass):
    """
    Find UP Contacts by email and report Commons eligibility, using the
    External Client App client-credentials token.
    """

    def __init__(self, client: SalesforceRestClient | None = None):
        self.client = client or SalesforceRestClient()
        self.contact_response: list[Contact] | None = None

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        return EMAIL_REGEX.match(email) is not None

    def _query_contacts(self, email: str) -> QueryResponse[Contact] | None:
        """Query Salesforce (or the cache) for Contacts with this email."""
        cache_key = f"{SEARCH_CACHE_PREFIX}{email}"
        raw = cache.get(cache_key, version=VERSION)

        if raw is None:
            raw = self.client.query(contact_soql(email))
            cache.set(
                cache_key,
                raw,
                timeout=settings.UP_ECA_CACHE_TIMEOUT,
                version=VERSION,
            )

        try:
            return TypeAdapter(QueryResponse[Contact]).validate_python(raw)
        except ValidationError:
            logger.exception("Error parsing UP contact query response")
            sentry_sdk.capture_exception()
            return None

    def search(self, email):
        return self.search_multiple([email])

    def search_multiple(self, emails):
        """
        Search for a Contact by each email in turn; the first hit wins.
        """
        for raw_email in emails:
            email = normalize_email(raw_email) if raw_email else None
            if not email or not self._is_valid_email(email):
                continue

            try:
                logger.info("Searching for %s in UP Contacts", email)
                response = self._query_contacts(email)
            except UPSalesforceError:
                logger.exception("UP contact lookup failed for %s", email)
                continue

            if response is None:
                continue

            self.contact_response = response.records

            if response.totalSize > 0:
                return {SYNC_KEY: response}

        return {SYNC_KEY: None}

    def get_sync_id(self, response: QueryResponse[Contact] | None):
        if response and response.totalSize > 0 and response.records:
            return response.records[0].AccountId
        return None

    def get_user_info(self, user_id):
        return self.contact_response

    def is_member(self, user_id) -> bool:
        contacts = self.get_user_info(user_id)
        if contacts:
            return bool(contacts[0].UP_Commons_Eligible__c)
        return False

    def groups(self, user_id) -> list[str]:
        return []

    def lookup(self, emails) -> MembershipLookup:
        """Search and summarise the result for reporting."""
        response = self.search_multiple(emails)[SYNC_KEY]
        account_id = self.get_sync_id(response)
        if not account_id and not (response and response.records):
            return MembershipLookup(found=False)

        contact = response.records[0]
        return MembershipLookup(
            found=True,
            matched_email=contact.Email,
            contact=contact,
            account_id=account_id,
            eligible=self.is_member(account_id),
        )
