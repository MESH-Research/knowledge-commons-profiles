"""
The UP API for synchronising user data
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from datetime import datetime

# ruff: noqa: TC003
from http import HTTPMethod
from typing import Generic
from typing import Literal
from typing import TypeVar

import requests
import sentry_sdk
from django.conf import settings
from django.core.cache import cache
from django.core.validators import validate_email
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import field_validator
from requests.adapters import HTTPAdapter
from rest_framework.status import HTTP_200_OK
from urllib3.util.retry import Retry

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import APIError
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import rate_limit

MEMBERS_URL = "query"
MAX_CALLS = 100
MAX_CALL_PERIOD = 60
# Simple but solid regex for validating most real-world email addresses
EMAIL_REGEX = re.compile(
    r"^(?P<local>[a-zA-Z0-9_.+-]+)@(?P<domain>[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$"
)
DATE_OFFSET = 5

logger = logging.getLogger(__name__)

# --- Helpers ---------------------------------------------------------------


def _parse_sf_datetime(value: str) -> datetime:
    """
    Salesforce emits datetimes like '2025-11-06T13:56:42.000+0000'
    (RFC3339-ish but the timezone is '+0000' not '+00:00').
    We normalize by inserting the colon in the offset if needed.
    """
    if value is None:
        return value  # type: ignore[return-value]
    # Already ISO-like with colon? Let fromisoformat try first.
    # ruff: noqa: BLE001
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.exception("Failed to parse datetime %s", value)
    except Exception:
        logger.exception("Failed to parse datetime %s", value)

    # Fix '+HHMM' -> '+HH:MM' (and '-HHMM' -> '-HH:MM')
    if (
        len(value) >= DATE_OFFSET
        and (value[-DATE_OFFSET] in ["+", "-"])
        and value[-3] != ":"
    ):
        value = (
            value[:-DATE_OFFSET] + value[-DATE_OFFSET:-2] + ":" + value[-2:]
        )
    # Remove trailing 'Z' variants if present (rare in SFDC REST)
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


# --- Core nested types -----------------------------------------------------


class SFAttributes(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["Account", "Contact"]
    # Salesforce often returns relative URLs here (not valid absolute URLs),
    # so use str.
    url: str


class SFAddress(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city: str | None = None
    country: str | None = None
    countryCode: str | None = None
    geocodeAccuracy: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    postalCode: str | None = None
    state: str | None = None
    stateCode: str | None = None
    street: str | None = None


# --- Account ---------------------------------------------------------------


class Account(BaseModel):
    """
    A pragmatic Salesforce Account model.

    Notes:
    - We strongly type the commonly used & standard fields.
    - All unmodeled fields (including org-specific __c fields) are accepted
    - via extra='allow'.
    - Datetime fields are parsed from Salesforce's '+0000' style offsets.
    """

    model_config = ConfigDict(
        extra="allow",  # keep unexpected / org-specific fields
        populate_by_name=True,  # allow both alias and field name # (not used)
        str_strip_whitespace=True,
    )

    # Nested
    attributes: SFAttributes
    BillingAddress: SFAddress | None = None
    ShippingAddress: SFAddress | None = None

    # Identifiers / ownership
    Id: str
    IsDeleted: bool
    MasterRecordId: str | None = None
    OwnerId: str | None = None
    RecordTypeId: str | None = None
    ParentId: str | None = None

    # Core business info
    Name: str
    Type: str | None = None
    AccountNumber: str | None = None
    Site: str | None = None
    Phone: str | None = None
    Fax: str | None = None
    Website: str | None = None
    PhotoUrl: str | None = None
    Industry: str | None = None
    AnnualRevenue: float | None = None
    NumberOfEmployees: int | None = None
    Ownership: str | None = None
    TickerSymbol: str | None = None
    Description: str | None = None
    Rating: str | None = None
    Sic: str | None = None
    SicDesc: str | None = None
    AccountSource: str | None = None
    Jigsaw: str | None = None
    JigsawCompanyId: str | None = None

    # Billing (flat fields)
    BillingStreet: str | None = None
    BillingCity: str | None = None
    BillingState: str | None = None
    BillingPostalCode: str | None = None
    BillingCountry: str | None = None
    BillingStateCode: str | None = None
    BillingCountryCode: str | None = None
    BillingLatitude: float | None = None
    BillingLongitude: float | None = None
    BillingGeocodeAccuracy: str | None = None

    # Shipping (flat fields)
    ShippingStreet: str | None = None
    ShippingCity: str | None = None
    ShippingState: str | None = None
    ShippingPostalCode: str | None = None
    ShippingCountry: str | None = None
    ShippingStateCode: str | None = None
    ShippingCountryCode: str | None = None
    ShippingLatitude: float | None = None
    ShippingLongitude: float | None = None
    ShippingGeocodeAccuracy: str | None = None

    # Timestamps & activity
    CreatedDate: datetime | None = None
    CreatedById: str | None = None
    LastModifiedDate: datetime | None = None
    LastModifiedById: str | None = None
    SystemModstamp: datetime | None = None
    LastActivityDate: date | None = None
    LastViewedDate: datetime | None = None
    LastReferencedDate: datetime | None = None

    # Example custom/extended fields from your payload (strongly typed
    # when obvious).
    # Everything else will still be accepted due to extra='allow'.
    Nickname__c: str | None = None
    Active__c: bool | None = None
    Email__c: str | None = None
    Statistics_Number__c: float | None = None
    Press_Number__c: str | None = None
    Membership_Type__c: str | None = None
    Membership_Category__c: str | None = None
    US_Distribution__c: bool | None = None
    Region__c: str | None = None
    Land_Grant_Institution__c: bool | None = None
    Reporting_Details__c: str | None = None
    Journals__c: str | None = None
    Journals_Published__c: float | None = None
    Small_Press__c: str | None = None
    Type_of_Order_Fulfillment__c: str | None = None
    Former_Affiliate_Memeber__c: bool | None = None
    Operating_Statistics_Participation__c: str | None = None
    Member_Institution_Type__c: str | None = None
    Compensation_Survey__c: str | None = None
    Directory_Files_Location__c: str | None = None
    Stats_Worksheet_Link__c: str | None = None
    Number_of_Titles_Available_OA__c: float | None = None
    OA_Program_Participation__c: str | None = None
    Dues_2017_2018__c: float | None = None
    Dues_2018_2019__c: float | None = None
    Dues_2019_20__c: float | None = None
    Dues_2020_21__c: float | None = None
    Dues_2021_22__c: float | None = None
    Title_Output_1999__c: float | None = None
    Title_Output_2000__c: float | None = None
    Title_Output_2001__c: float | None = None
    Title_Output_2002__c: float | None = None
    Title_Output_2003__c: float | None = None
    Title_Output_2004__c: float | None = None
    Title_Output_2005__c: float | None = None
    Title_Output_2006__c: float | None = None
    Title_Output_2007__c: float | None = None
    Title_Output_2008__c: float | None = None
    Title_Output_2009__c: float | None = None
    Title_Output_2010__c: float | None = None
    Title_Output_2011__c: float | None = None
    Title_Output_2012__c: float | None = None
    Title_Output_2013__c: float | None = None
    Title_Output_2014__c: float | None = None
    Title_Output_2015__c: float | None = None
    Title_Output_2016__c: float | None = None
    Title_Output_2017__c: float | None = None
    Title_Output_2018__c: float | None = None
    Title_Output_2019__c: float | None = None
    Title_Output_2021__c: float | None = None
    Title_Output_2022__c: float | None = None
    Tit__c: float | None = None  # appears to be title output metric in sample

    # --- Validators for datetime/date fields --------------------------------

    @field_validator(
        "CreatedDate",
        "LastModifiedDate",
        "SystemModstamp",
        "LastViewedDate",
        "LastReferencedDate",
        mode="before",
    )
    @classmethod
    def _parse_sfdc_dt(cls, v):
        if v is None or isinstance(v, datetime):
            return v
        return _parse_sf_datetime(str(v))

    @field_validator("LastActivityDate", mode="before")
    @classmethod
    def _parse_sfdc_date(cls, v):
        if v is None or isinstance(v, date):
            return v
        # Accept 'YYYY-MM-DD'
        return date.fromisoformat(str(v))


class Contact(BaseModel):
    """Salesforce Contact record."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    attributes: SFAttributes
    Id: str
    Name: str
    Email: str | None = None
    AccountId: str | None = None
    Current_Staff__c: bool | None = None


T = TypeVar("T")


# ruff: noqa: N815
class SalesforceQueryResponse(BaseModel, Generic[T]):
    totalSize: int
    done: bool
    records: list[T]


class UP(SyncClass):
    """
    The UP API.

    The API has several methods: search (will find a record by email),
    get_user_info (will find a record by id), is_member (returns a boolean of
    whether the user is a member) and groups (returns a user's groups).
    """

    def __init__(self):
        """
        Constructor
        """
        self.base_url = settings.UP_API_BASE_URL
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
        Make a request to the UP API
        """
        # refresh the access key
        result = self._refresh_salesforce_token()

        if "access_token" in result:
            settings.UP_API_TOKEN = result["access_token"]

        timeout = 30
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings.UP_API_TOKEN,
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

    def _query_up_api(
        self,
        attributes: dict[str, str],
        suffix: str | None = None,
        cache_key: str | None = None,
    ):
        """
        Query the UP API
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

            resp = response.json()

            if "errorCode" in resp:
                raise APIError(resp["errorCode"])

            cache_timeout = settings.UP_CACHE_TIMEOUT

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
            message = f"Request to UP API failed: {e}"
            logger.exception(message)
            raise APIError(message) from e

        if response.status_code == HTTP_200_OK:
            logger.debug("UP response: %s", response.content)
            return response.content

        message = f"Received {response.status_code} response"
        logger.error(message)
        raise APIError(message)

    def is_member(self, user_id: str) -> bool:
        """
        Check if a user is a member
        """
        response: Account | dict = self.get_user_info(user_id)

        return bool(response.Id)

        return False

    def _is_valid_email(self, email: str) -> bool:
        """Return True if the given string is a valid email address."""
        return EMAIL_REGEX.match(email) is not None

    def search_multiple(self, emails) -> SalesforceQueryResponse | dict:
        """
        Search for a user
        :param emails: the emails to search for; first hit will be returned
        """
        for email in emails:
            cache_key = f"UP_api_search_{email}"

            # Validate email
            if not self._is_valid_email(email):
                continue

            # ruff: noqa: S608
            search_params = {
                "q": f"SELECT Id, Name, Email, AccountId, Current_Staff__c "
                f"FROM Contact "
                f"WHERE Email = '{email}'",
            }

            try:
                logger.info("Searching for %s in UP Contacts", email)
                result = self._query_up_api(search_params, cache_key=cache_key)

                adapted: SalesforceQueryResponse[Contact] = (
                    self._process_adapter(
                        SalesforceQueryResponse[Contact], result
                    )
                )

                if adapted.totalSize > 0:
                    return {"UP": adapted}

            except APIError:
                continue
        return {"UP": None}

    def get_sync_id(self, response: SalesforceQueryResponse[Contact]):
        """
        Get a sync ID from the api response
        :param response: the response from the API
        """

        if response and response.totalSize > 0:
            return response.records[0].AccountId
        return None

    def search(self, email) -> SalesforceQueryResponse | dict:
        """
        Search for a user
        :param email: the email to search for
        """
        try:
            validate_email(email)
        except ValidationError as ve:
            message = f"Invalid email address: {email}"
            raise ValueError(message) from ve

        cache_key = f"UP_api_search_{email}"

        search_params = {
            "email": email,
        }

        try:
            result = self._query_up_api(search_params, cache_key=cache_key)
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(SalesforceQueryResponse, result)

    @staticmethod
    def _process_adapter(type_adapter, result):
        """
        Process the response
        """
        try:
            adapter = TypeAdapter(type_adapter)
            response = adapter.validate_json(result)

        except ValidationError:
            logger.exception("Error parsing UP search response")
            sentry_sdk.capture_exception()
            return {}
        except json.JSONDecodeError:
            logger.exception("Invalid JSON response from UP API")
            sentry_sdk.capture_exception()
            return {}

        return response

    def get_user_info(self, up_id: str | int) -> Account | dict:
        """
        Search for a user
        """
        try:
            up_id = str(up_id)
        except ValueError:
            logger.exception("Invalid UP ID (must be string or int)")
            return {}

        cache_key = f"UP_api_user_info_{up_id}"

        search_params = {}

        try:
            result = self._query_up_api(
                search_params,
                suffix="sobjects/Account/" + up_id,
                cache_key=cache_key,
            )
        except APIError:
            return {}

        if not result:
            return {}

        return self._process_adapter(Account, result)

    def groups(self, user_id: str | int) -> list[str]:
        """
        Get a user's groups
        """
        return []

    def _refresh_salesforce_token(self):
        url = "https://aupresses.my.salesforce.com/services/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.UP_CLIENT_ID,
            "client_secret": settings.UP_CLIENT_SECRET,
            "refresh_token": settings.UP_REFRESH_TOKEN,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        timeout = 30

        resp = requests.post(url, data=data, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
