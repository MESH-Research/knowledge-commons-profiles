"""
The ARLISNA API for synchronising user data
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC
from datetime import datetime
from http import HTTPMethod
from typing import TYPE_CHECKING

import dateutil
import requests
import sentry_sdk
from django.conf import settings
from django.core.cache import cache
from django.core.validators import validate_email
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import model_validator
from requests.adapters import HTTPAdapter
from rest_framework.status import HTTP_200_OK
from urllib3.util.retry import Retry

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import APIError
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import rate_limit

if TYPE_CHECKING:
    from decimal import Decimal


MEMBERS_URL = "members"
MAX_CALLS = 100
MAX_CALL_PERIOD = 60

logger = logging.getLogger(__name__)


class _BaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _empty_strings_to_none(cls, value):
        def transform(v):
            if isinstance(v, dict):
                return {k: transform(vv) for k, vv in v.items()}
            if isinstance(v, list):
                return [transform(vv) for vv in v]
            if v == "":
                return None
            return v

        return transform(value)


class Address(_BaseModel):
    Address1: str | None = None
    Address2: str | None = None
    City: str | None = None
    ZipCode: str | None = None
    StateProvince: str | None = None
    Country: str | None = None


class MemberTypeInfo(_BaseModel):
    UniqueID: str
    Name: str
    Description: str | None = None
    ForCompanies: bool


class CustomFieldEntry(_BaseModel):
    CustomerUniqueID: str
    CustomFieldUniqueID: str
    CustomFieldName: str
    Value: str | None = None
    IsSumOfChildren: bool


class GroupMembership(_BaseModel):
    GroupUniqueID: str
    GroupName: str
    InheritingMember: bool
    JoinDate: datetime | None = None


class MemberResult(_BaseModel):
    # Identifiers & names
    UniqueID: str
    ImportID: str | None = None
    InternalIdentifier: int | None = None
    ParentCustomerUniqueID: str | None = None
    ParentMemberName: str | None = None
    Name: str | None = None
    FirstName: str | None = None
    MiddleName: str | None = None
    LastName: str | None = None
    Suffix: str | None = None

    # Status
    Active: bool | None = None
    Approved: bool | None = None
    CustomerType: str | None = None
    MemberStatus: str | None = None
    MemberSubStatus: str | None = None
    IsInstructor: bool | None = None
    IncompleteSignup: bool | None = None
    FeaturedDirectoryListing: bool | None = None
    HideOnWebsite: bool | None = None
    HideContactInformation: bool | None = None
    ManagementAccessForCompanies: list[str] = Field(default_factory=list)

    # Contact
    Email: str | None = None
    AccountEmail: str | None = None
    Phone: str | None = None
    Mobile: str | None = None
    Fax: str | None = None
    Website: str | None = None
    County: str | None = None

    # Addresses
    BillingAddress: Address | None = None
    ShippingAddress: Address | None = None
    PersonalEmail: str | None = None
    PersonalPhone: str | None = None
    PersonalMobile: str | None = None
    PersonalAddress: Address | None = None

    # Social / profile
    FacebookUrl: str | None = None
    LinkedInUrl: str | None = None
    InstagramHandle: str | None = None
    TwitterHandle: str | None = None
    MemberProfile: str | None = None
    JobTitle: str | None = None
    Image: str | None = None
    Credentials: str | None = None
    Title: str | None = None
    Notes: str | None = None

    # Membership dates
    OriginalJoinDate: datetime | None = None
    MemberSince: datetime | None = None
    MembershipExpires: datetime | None = None

    # Dues / billing
    DuesPayerUniqueID: str | None = None
    UseParentBilling: bool | None = None
    UseParentShipping: bool | None = None
    UnsubscribeFromEmails: bool | None = None
    UnsubscribeFromSignupEmails: bool | None = None
    AutoRenew: bool | None = None
    AutoPay: bool | None = None
    QuickBooksID: str | None = None
    Taxable: bool | None = None
    TaxExemptionReason: str | None = None
    ProhibitInvoicing: bool | None = None
    OpenDuesBalance: Decimal | None = None
    OverdueDuesBalance: Decimal | None = None
    DefaultDuesPayerOverride: str | None = None

    # Member type(s)
    MemberType: MemberTypeInfo | None = None
    EffectiveMemberType: MemberTypeInfo | None = None

    # Custom fields
    CustomFields: dict[str, CustomFieldEntry] = Field(default_factory=dict)

    # System/meta
    SpecifiedSystemFields: list[str] = Field(default_factory=list)
    FamilyTreeUniqueID: str | None = None
    PrimaryContactUniqueId: str | None = None
    BillingContactUniqueId: str | None = None
    CreatedDate: datetime | None = None
    LastUpdatedDate: datetime | None = None
    LastSegmentUpdatedDate: datetime | None = None

    # NPS
    AverageNpsScore: float | None = None
    LastNpsScore: float | None = None
    LastNpsScoreDate: datetime | None = None
    LastNpsFeedback: str | None = None

    # Collections
    DirectoryGallery: list[str] = Field(default_factory=list)
    Awards: list[str] = Field(default_factory=list)
    VolunteerWorks: list[str] = Field(default_factory=list)
    Education: list[str] = Field(default_factory=list)
    Groups: list[GroupMembership] = Field(default_factory=list)
    Committees: list[str] = Field(default_factory=list)


class MembersSearchResponse(_BaseModel):
    TotalCount: int
    Results: list[MemberResult]


MemberResult.model_rebuild()
MembersSearchResponse.model_rebuild()


class ARLISNA(SyncClass):
    """
    The ARLISNA API.

    The API has several methods: search (will find a record by email),
    get_user_info (will find a record by id), is_member (returns a boolean of
    whether the user is a member) and groups (returns a user's groups).
    """

    def __init__(self):
        """
        Constructor
        """
        self.base_url = settings.ARLISNA_API_BASE_URL
        self.session = requests.Session()

        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
            pool_block=False,
        )
        self.session.mount("https://", adapter)

    @rate_limit(max_calls=MAX_CALLS, period=MAX_CALL_PERIOD)
    def _make_rest_request(self, url, http_method=HTTPMethod.GET, params=None):
        """
        Make a request to the ARLISNA API
        """
        timeout = 30
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic " + settings.ARLISNA_API_TOKEN,
        }

        response = self.session.request(
            method=http_method,
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
            verify=True,
        )
        response.raise_for_status()

        return response

    def _query_arlisna_api(
        self,
        attributes: dict[str, str],
        suffix: str | None = None,
        cache_key: str | None = None,
    ):
        """
        Query the ARLISNA API
        :param attributes:
        :return:
        """

        if cache_key:
            cached_response = cache.get(cache_key, version=VERSION)

            if cached_response is not None:
                return cached_response

        suffix = suffix if suffix else MEMBERS_URL
        url = self.base_url + suffix

        try:
            response = self._make_rest_request(
                url, HTTPMethod.GET, params=attributes
            )

            cache_timeout = settings.ARLISNA_CACHE_TIMEOUT

            if "Cache-Control" in response.headers:
                # Parse max-age from Cache-Control header
                match = re.search(
                    r"max-age=(\d+)", response.headers["Cache-Control"]
                )
                if match:
                    cache_timeout = min(int(match.group(1)), cache_timeout)

            if cache_key:
                cache.set(
                    cache_key,
                    response.content,
                    timeout=cache_timeout,
                    version=VERSION,
                )

        except requests.exceptions.RequestException as e:
            message = f"Request to ARLISNA API failed: {e}"
            logger.exception(message)
            raise APIError(message) from e

        if response.status_code == HTTP_200_OK:
            logger.debug("ARLISNA response: %s", response.content)
            return response.content

        message = f"Received {response.status_code} response"
        logger.error(message)
        raise APIError(message)

    def is_member(self, user_id: str) -> bool:
        """
        Check if a user is a member
        """
        response: MembersSearchResponse | dict = self.get_user_info(user_id)

        if response.TotalCount > 0:
            # parse response.data[0].membership.expiring_date into a date
            # and check if it is in the future
            try:
                expiring_date = dateutil.parser.parse(
                    str(response.Results[0].MembershipExpires)
                ).astimezone(tz=UTC)
                today = datetime.now(tz=UTC)

            except (ValueError, IndexError, AttributeError):
                logger.exception("Error parsing date in ARLISNA response")
                return False
            else:
                return expiring_date > today

        return False

    def search_multiple(self, emails) -> MembersSearchResponse | dict:
        """
        Search for a user
        :param emails: the emails to search for; first hit will be returned
        """
        for email in emails:
            cache_key = f"ARLISNA_api_search_{email}"

            search_params = {
                "email": email,
            }

            try:
                logger.info("Searching for %s in ARLISNA", email)
                result = self._query_arlisna_api(
                    search_params, cache_key=cache_key
                )

                adapted: MembersSearchResponse = self._process_adapter(
                    MembersSearchResponse, result
                )

                if adapted.TotalCount > 0:
                    return {"ARLISNA": adapted}

            except APIError:
                continue
        return {"ARLISNA": None}

    def get_sync_id(self, response: MembersSearchResponse):
        """
        Get a sync ID from the api response
        :param response: the response from the API
        """

        if response and response.TotalCount > 0:
            return response.Results[0].Email
        return None

    def search(self, email) -> MembersSearchResponse | dict:
        """
        Search for a user
        :param email: the email to search for
        """
        try:
            validate_email(email)
        except ValidationError as ve:
            message = f"Invalid email address: {email}"
            raise ValueError(message) from ve

        cache_key = f"ARLISNA_api_search_{email}"

        search_params = {
            "email": email,
        }

        try:
            result = self._query_arlisna_api(
                search_params, cache_key=cache_key
            )
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(MembersSearchResponse, result)

    @staticmethod
    def _process_adapter(type_adapter, result):
        """
        Process the response
        """
        try:
            adapter = TypeAdapter(type_adapter)
            response = adapter.validate_json(result)

        except ValidationError:
            logger.exception("Error parsing ARLISNA search response")
            sentry_sdk.capture_exception()
            return {}
        except json.JSONDecodeError:
            logger.exception("Invalid JSON response from ARLISNA API")
            sentry_sdk.capture_exception()
            return {}

        return response

    def get_user_info(
        self, arlisna_id: str | int
    ) -> MembersSearchResponse | dict:
        """
        Search for a user
        """
        try:
            arlisna_id = str(arlisna_id)
        except ValueError:
            logger.exception("Invalid ARLISNA ID (must be string or int)")
            return {}

        cache_key = f"ARLISNA_api_user_info_{arlisna_id}"

        search_params = {"email": arlisna_id}

        try:
            result = self._query_arlisna_api(
                search_params,
                suffix="members",
                cache_key=cache_key,
            )
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(MembersSearchResponse, result)

    def groups(self, user_id: str | int) -> list[str]:
        """
        Get a user's groups
        """
        return []
