"""
The MLA API for sunchronising user data
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import UTC
from datetime import datetime
from typing import Literal
from urllib import parse
from urllib.parse import urlencode

import requests
import sentry_sdk
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel
from pydantic import TypeAdapter
from pydantic import ValidationError
from starlette.status import HTTP_200_OK

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass

logger = logging.getLogger(__name__)


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
    email_visible: Literal["Y", "N"] | None = None
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
        self.base_url = "https://api.mla.org/2/"

    @staticmethod
    def _make_rest_request(url, http_method="GET", params=None):
        """
        Make a request to the MLA API
        """
        timeout = 30
        headers = {"Content-Type": "application/json"}

        response = requests.request(
            method=http_method,
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
            verify=False,  # Disable SSL verification
        )
        response.raise_for_status()

        return {
            "status": response.status_code,
            "body": response.text,
            "response_object": response,
        }

    def _query_mla_api(self, attributes, suffix=None):
        """
        Query the MLA API
        :param attributes:
        :return:
        """
        suffix = suffix if suffix else "members"
        url = self.base_url + suffix

        self._sign_request("GET", attributes, suffix=suffix)

        try:
            response = self._make_rest_request(url, "GET", attributes)
        except requests.exceptions.RequestException as e:
            message = f"Request to MLA API failed: {e}"
            logger.exception(message)
            return {}

        if response["status"] == HTTP_200_OK:
            logger.debug("MLA response: %s", response["body"])
            return response["body"]

        message = f"Received {response['status']} response"
        logger.error(message)
        return {}

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
            try:
                expiring_date = datetime.strptime(
                    response.data[0].membership.expiring_date,
                    "%d/%m/%Y",
                ).astimezone(UTC)
                today = datetime.now(tz=UTC)

                if expiring_date > today:
                    return True
            except ValueError:
                pass

            return True

        return False

    def search(self, email) -> SearchApiResponse | CommonErrorResponse | dict:
        """
        Search for a user
        :param email: the email to search for
        """
        cache_key = f"mla_search_{email}"
        cached_response = cache.get(cache_key, version=VERSION)

        if cached_response is not None:
            return cached_response

        search_params = {
            "email": email,
            "membership_status": "ALL",
            "timestamp": time.time(),
            "key": settings.MLA_API_KEY,
        }

        result = self._query_mla_api(search_params)

        try:
            adapter = TypeAdapter(SearchApiResponse)
            response = adapter.validate_python(json.loads(result))

            cache.set(
                key=cache_key,
                value=response,
                timeout=settings.MLA_CACHE_TIMEOUT,
                version=VERSION,
            )

        except ValidationError:
            logger.exception("Error parsing MLA search response")
            sentry_sdk.capture_exception()
            return {}
        else:
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

        cache_key = f"mla_user_info_{mla_id}"
        cached_response = cache.get(cache_key, version=VERSION)

        if cached_response is not None:
            return cached_response

        search_params = {
            "timestamp": time.time(),
            "key": settings.MLA_API_KEY,
        }

        result = self._query_mla_api(search_params, suffix=f"members/{mla_id}")

        try:
            adapter = TypeAdapter(MemberResponse)
            response = adapter.validate_python(json.loads(result))

            cache.set(
                key=cache_key,
                value=response,
                timeout=settings.MLA_CACHE_TIMEOUT,
                version=VERSION,
            )

        except ValidationError:
            logger.exception("Error parsing MLA ID response")
            sentry_sdk.capture_exception()
            return {}

        else:
            return response

    def _sign_request(self, http_method, params, suffix=None):
        """
        Append signature to input "params"
        """
        suffix = suffix if suffix else "members"

        url = self.base_url + suffix + "?" + urlencode(params)
        logger.debug("Building signature for %s", url)

        base_string = f"{http_method}&{parse.quote(url, safe='')}"

        api_signature = hmac.new(
            settings.MLA_API_SECRET.encode(),
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        params["signature"] = api_signature
        return api_signature

    def groups(self, user_id) -> list[str]:
        """
        Get a user's groups
        """
        return []
