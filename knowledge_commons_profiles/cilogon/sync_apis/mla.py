"""
The MLA API for synchronising user data
"""

import hashlib
import hmac
import json
import logging
import re
import time
from datetime import UTC
from datetime import datetime
from http import HTTPMethod
from typing import Literal
from urllib import parse
from urllib.parse import urlencode

import requests
import sentry_sdk
from dateutil import parser
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from pydantic import BaseModel
from pydantic import TypeAdapter
from pydantic import ValidationError
from requests.adapters import HTTPAdapter
from rest_framework.status import HTTP_200_OK
from urllib3.util.retry import Retry

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import APIError
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import rate_limit

logger = logging.getLogger(__name__)

MEMBERS_URL = "members"
MAX_CALLS = 100
MAX_CALL_PERIOD = 60


class CommonMeta(BaseModel):
    """
    Common metadata
    """

    status: Literal["success", "error"]
    code: str
    message: str | None


class SimpleAddress(BaseModel):
    """
    Simple address returned by search
    """

    type: str
    rank: str | None = None
    institution: str | None = None
    city: str
    state: str | None = None
    zip: str | None = None
    country: str
    address1: str | None = None


class SimpleGeneralInfo(BaseModel):
    """
    Simple general info returned by search
    """

    title: str
    first_name: str
    last_name: str
    suffix: str | None = None
    email: str | None = ""
    email_visible: Literal["Y", "N", ""] | None = None
    email_shareable: str | None = None
    phone: str | None = ""
    web_site: str | None = ""
    addresses: list[SimpleAddress]


class SimpleMembershipInfo(BaseModel):
    """
    Simple membership info returned by search
    """

    class_code: str
    year_joined: str
    membership_years: str


class SimpleSearchResult(BaseModel):
    """
    Simple search result
    """

    id: str
    membership: SimpleMembershipInfo
    general: SimpleGeneralInfo


class SimpleDataBlock(BaseModel):
    """
    Simple data block
    """

    total_num_results: int
    search_results: list[SimpleSearchResult]


class SimpleSuccessResponse(BaseModel):
    """
    Simple success response
    """

    meta: CommonMeta
    data: list[SimpleDataBlock]


class DetailedAddress(BaseModel):
    """
    Detailed address returned by id
    """

    id: str | None = None
    type: str
    hidden: str | None = None
    send_mail: str | None = None
    affiliation: str | None = None
    ringgold_id: str | None = None
    display_affil: str | None = None
    department: str | None = None
    other_dept: str | None = None
    department_other: str | None = None
    rank: str | None = None
    display_rank: str | None = None
    line1: str | None = None
    line2: str | None = None
    line3: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    country_code: str | None = None


class DetailedGeneralInfo(BaseModel):
    """
    Detailed general info returned by id
    """

    title: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    suffix: str | None = None
    email: str | None = None
    email_visible: str | None = None
    email_shareable: str | None = None
    email_digest: str | None = None
    email_convention: str | None = None
    email_unsubscribe: str | None = None
    online_newsletter: str | None = None
    phone: str | None = None
    web_site: str | None = None
    joined_commons: str | None = None
    donor_exclude: str | None = None
    orcid: str | None = None
    new_mbr: str | None = None


class DetailedMembershipInfo(BaseModel):
    """
    Detailed membership info returned by id
    """

    class_code: str
    year_joined: str | None = None
    starting_date: str | None = None
    expiring_date: str | None = None
    membership_years: str | None = None
    arb_status: str | None = None
    arb_bill_date: str | None = None


class Authentication(BaseModel):
    """
    Authentication returned by id
    """

    username: str
    password: str
    membership_status: str


class PublicationAccessEntry(BaseModel):
    """
    Publication access returned by id
    """

    type: str
    access: dict[str, str]


class PublicationHistoryEntry(BaseModel):
    """
    Publication history returned by id
    """

    year: str
    pub_code: str
    name: str
    price: str


class Pmla(BaseModel):
    """
    PMLA returned by id
    """

    pmla_sub: str | None = None
    end_date: str | None = None
    may_renew_on: str | None = None
    renewal_price: str | None = None


class Organization(BaseModel):
    """
    Organization returned by id
    """

    id: str
    name: str
    convention_code: str
    position: str
    type: str
    exclude_from_commons: str | None = None
    primary: str | None = None


class DuesHistoryEntry(BaseModel):
    """
    Dues history returned by id
    """

    class_code: str
    name: str
    starting_date: str
    expiring_date: str
    date_paid: str
    joint_mem_id: str | None = None
    joint_name: str | None = None
    dues_paid: str
    joint_sub_cls_code: str | None = None


class ContributionHistoryEntry(BaseModel):
    """
    Contribution history returned by id
    """

    type: str
    contribution_year: str
    fund_code: str
    name: str
    amount: str
    date_paid: str


class Language(BaseModel):
    """
    Language returned by id
    """

    code: str
    name: str
    primary: str | None = None


class MemberProfile(BaseModel):
    """
    Member profile returned by id
    """

    id: str
    authentication: Authentication
    membership: DetailedMembershipInfo
    general: DetailedGeneralInfo
    addresses: list[DetailedAddress]
    publications_access: list[PublicationAccessEntry]
    publications_history: list[PublicationHistoryEntry]
    pmla: Pmla
    organizations: list[Organization]
    dues_history: list[DuesHistoryEntry]
    contributions_history: list[ContributionHistoryEntry]
    languages: list[Language]


class MemberResponseSuccess(BaseModel):
    """
    Success response
    """

    meta: CommonMeta
    data: list[MemberProfile]


class CommonErrorResponse(BaseModel):
    """
    Common error response
    """

    meta: CommonMeta
    data: list = []


SearchApiResponse = SimpleSuccessResponse | CommonErrorResponse
MemberResponse = MemberResponseSuccess | CommonErrorResponse


class MLA(SyncClass):
    """
    The MLA API.

    The API has several methods: search (will find a record by email),
    get_user_info (will find a record by id), is_member (returns a boolean of
    whether the user is a member) and groups (returns a user's groups).
    """

    def __init__(self):
        """
        Constructor
        """
        self.base_url = settings.MLA_API_BASE_URL
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
        Make a request to the MLA API
        """
        timeout = 30
        headers = {"Content-Type": "application/json"}

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

    def _query_mla_api(
        self,
        attributes: dict[str, str],
        suffix: str | None = None,
        cache_key: str | None = None,
    ):
        """
        Query the MLA API
        :param attributes:
        :return:
        """
        if cache_key:
            cached_response = cache.get(cache_key, version=VERSION)

            if cached_response is not None:
                return cached_response

        suffix = suffix if suffix else MEMBERS_URL
        url = self.base_url + suffix

        # copy so as not to mutate the original dictionary
        signed_attributes = attributes.copy()
        signed_attributes["signature"] = self._get_signature(
            HTTPMethod.GET, attributes, suffix=suffix
        )

        try:
            response = self._make_rest_request(
                url, HTTPMethod.GET, signed_attributes
            )

            cache_timeout = settings.MLA_CACHE_TIMEOUT

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
            message = f"Request to MLA API failed: {e}"
            logger.exception(message)
            raise APIError(message) from e

        if response.status_code == HTTP_200_OK:
            logger.debug("MLA response: %s", response.content)
            return response.content

        message = f"Received {response.status_code} response"
        logger.error(message)
        raise APIError(message)

    def is_member(self, user_id: str | int) -> bool:
        """
        Check if a user is a member
        """
        response: MemberResponse | CommonErrorResponse | dict = (
            self.get_user_info(user_id)
        )

        if (
            getattr(response, "meta", None) is not None
            and response.meta.status == "success"
        ):
            # parse response.data[0].membership.expiring_date into a date
            # and check if it is in the future
            if hasattr(response.data[0], "membership"):
                expiring_raw = response.data[0].membership.expiring_date
                if not expiring_raw:
                    return False
                dt = parser.parse(expiring_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt > datetime.now(tz=UTC)

        return False

    def search_multiple(
        self, emails
    ) -> SearchApiResponse | CommonErrorResponse | dict:
        """
        Search for a user
        :param emails: the emails to search for; first hit will be returned
        """
        for email in emails:
            cache_key = f"MLA_api_search_{email}"

            search_params = {
                "email": email,
                "membership_status": "ALL",
                "timestamp": time.time(),
                "key": settings.MLA_API_KEY,
            }

            try:
                logger.info("Searching for %s in MLA", email)
                result = self._query_mla_api(
                    search_params, cache_key=cache_key
                )

                adapted = self._process_adapter(SearchApiResponse, result)

                if (
                    hasattr(adapted, "meta")
                    and adapted.meta.status == "success"
                    and hasattr(adapted.data[0], "total_num_results")
                    and adapted.data[0].total_num_results > 0
                ):
                    return {"MLA": adapted}

            except APIError:
                continue
        return {"MLA": None}

    def get_sync_id(self, response):
        """
        Get a sync ID from the api response
        :param response: the response from the API
        """
        logger.info("MLA sync_id response: %s", response)
        if response:
            return response.data[0].search_results[0].id
        return None

    def search(self, email) -> SearchApiResponse | CommonErrorResponse | dict:
        """
        Search for a user
        :param email: the email to search for
        """
        try:
            validate_email(email)
        except DjangoValidationError as ve:
            message = f"Invalid email address: {email}"
            raise ValueError(message) from ve

        cache_key = f"MLA_api_search_{email}"

        search_params = {
            "email": email,
            "membership_status": "ALL",
            "timestamp": time.time(),
            "key": settings.MLA_API_KEY,
        }

        try:
            result = self._query_mla_api(search_params, cache_key=cache_key)
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(SearchApiResponse, result)

    @staticmethod
    def _process_adapter(type_adapter, result):
        """
        Process the response
        """
        try:
            adapter = TypeAdapter(type_adapter)
            response = adapter.validate_json(result)

        except ValidationError:
            logger.exception("Error parsing MLA search response")
            sentry_sdk.capture_exception()
            return {}
        except json.JSONDecodeError:
            logger.exception("Invalid JSON response from MLA API")
            sentry_sdk.capture_exception()
            return {}

        return response

    def get_user_info(
        self, mla_id: str | int
    ) -> MemberResponse | CommonErrorResponse | dict:
        """
        Search for a user
        """
        try:
            mla_id = str(mla_id)
        except ValueError:
            logger.exception("Invalid MLA ID (must be string or int)")
            return {}

        cache_key = f"MLA_api_user_info_{mla_id}"

        search_params = {
            "timestamp": time.time(),
            "key": settings.MLA_API_KEY,
        }

        try:
            result = self._query_mla_api(
                search_params,
                suffix=f"{MEMBERS_URL}/{mla_id}",
                cache_key=cache_key,
            )
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(MemberResponse, result)

    def _get_signature(self, http_method, params, suffix=None):
        """
        Append signature to input "params"
        """
        suffix = suffix if suffix else MEMBERS_URL

        url = self.base_url + suffix + "?" + urlencode(params)
        logger.debug("Building signature for %s", url)

        base_string = f"{http_method}&{parse.quote(url, safe='')}"

        return hmac.new(
            settings.MLA_API_SECRET.encode(),
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()

    def groups(self, user_id: str | int) -> list[str]:
        """
        Get a user's groups
        """
        return []
