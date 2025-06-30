import json
import logging
from enum import Enum
from typing import Any

import requests
from django.conf import settings
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import conint
from pydantic import field_validator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Enum for event types"""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    ASSOCIATED = "associated"


class UserUpdate(BaseModel):
    """Model for user updates"""

    id: str = Field(..., min_length=1, description="User identifier")
    event: EventType = Field(..., description="Event type")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is not empty or just whitespace"""
        if not v.strip():
            message = "User ID cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {"id": "myusername", "event": "updated"}
        },
    )


class AssociationUpdate(BaseModel):
    """Model for association updates"""

    id: str = Field(..., min_length=1, description="Sub identifier")
    kc_id: str = Field(..., min_length=1, description="KC ID")
    event: EventType = Field(..., description="Event type")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is not empty or just whitespace"""
        if not v.strip():
            message = "User ID cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    @field_validator("kc_id")
    @classmethod
    def validate_kc_id(cls, v: str) -> str:
        """Ensure KC ID is not empty or just whitespace"""
        if not v.strip():
            message = "KC ID cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "id": "http://cilogon.org/serverE/users/329380",
                "kc_id": "martin_eve",
                "event": "associated",
            }
        },
    )


class GroupUpdate(BaseModel):
    """Model for group updates"""

    id: str = Field(..., min_length=1, description="Group identifier")
    event: EventType = Field(..., description="Event type")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Ensure ID is not empty or just whitespace"""
        if not v.strip():
            message = "Group ID cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={"example": {"id": "1234", "event": "updated"}},
    )


class AssociationsPayload(BaseModel):
    """Model for the complete associations payload"""

    idp: str = Field(..., min_length=1, description="Identity provider")
    associations: dict[str, list[dict[str, str]]] = Field(
        ..., description="associations object"
    )

    @field_validator("idp")
    @classmethod
    def validate_idp(cls, v: str) -> str:
        """Ensure IDP is not empty or just whitespace"""
        if not v.strip():
            message = "IDP cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    @field_validator("associations")
    @classmethod
    def validate_updates(
        cls, v: dict[str, list[dict[str, str]]]
    ) -> dict[str, list[dict[str, str]]]:
        """Ensure at least one update is provided"""
        if not v or (not v.get("associations")):
            message = "At least one association is required"
            raise ValueError(message)
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "idp": "cilogon",
                "updates": {
                    "users": [
                        {"id": "myusername", "event": "updated"},
                        {"id": "anotherusername", "event": "created"},
                    ],
                    "groups": [{"id": "1234", "event": "updated"}],
                },
            }
        }
    )


class UpdatePayload(BaseModel):
    """Model for the complete update payload"""

    idp: str = Field(..., min_length=1, description="Identity provider")
    updates: dict[str, list[dict[str, str]]] = Field(
        ..., description="Updates object"
    )

    @field_validator("idp")
    @classmethod
    def validate_idp(cls, v: str) -> str:
        """Ensure IDP is not empty or just whitespace"""
        if not v.strip():
            message = "IDP cannot be empty or whitespace"
            raise ValueError(message)
        return v.strip()

    @field_validator("updates")
    @classmethod
    def validate_updates(
        cls, v: dict[str, list[dict[str, str]]]
    ) -> dict[str, list[dict[str, str]]]:
        """Ensure at least one update is provided"""
        if not v or (not v.get("users") and not v.get("groups")):
            message = "At least one user or group update is required"
            raise ValueError(message)
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "idp": "cilogon",
                "updates": {
                    "users": [
                        {"id": "myusername", "event": "updated"},
                        {"id": "anotherusername", "event": "created"},
                    ],
                    "groups": [{"id": "1234", "event": "updated"}],
                },
            }
        }
    )


class APIClientConfig(BaseModel):
    """Configuration for API client"""

    base_url: HttpUrl
    timeout: conint(gt=0) = 30
    max_retries: conint(ge=0) = 3
    backoff_factor: float = Field(0.3, ge=0)
    status_forcelist: list[int] | None = None

    class Config:
        validate_assignment = True


class APIResponse(BaseModel):
    """Model for API response"""

    status_code: int
    data: dict[str, Any] | None = None
    raw_response: str | None = None
    error: str | None = None


class APIClient:
    """Client for sending updates to the API endpoint"""

    def __init__(self, config: APIClientConfig):
        """
        Initialize the API client.

        Args:
            config: API client configuration
        """
        self.config = config
        self.base_url = str(config.base_url).rstrip("/")
        self.timeout = config.timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()

        status_forcelist = self.config.status_forcelist or [
            408,
            429,
            500,
            502,
            503,
            504,
        ]

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["POST", "GET", "PUT", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def post_webhook(self, group_updates, user_updates):
        """
        A wrapper for the send_updates function that posts the updates
        :param group_updates: the group updates
        :param user_updates: the user updates
        :return: the response
        """
        if not settings.WEBHOOK_TOKEN:
            message = "Missing webhook token"
            logger.error(message)
            raise ValueError(message)

        try:
            # Send updates
            response = self.send_updates(
                endpoint="/api/webhooks/user_data_update",
                idp="cilogon",
                users=user_updates,
                groups=group_updates,
                headers={
                    "Authorization": "Bearer " + settings.WEBHOOK_TOKEN,
                },
            )

            if response.data:
                message = "Success! Response: %s"
                logger.info(message, json.dumps(response.data, indent=2))
            else:
                message = "Success! Raw response: %s"
                logger.info(message, response.raw_response)

        except ValueError:
            message = "Validation error: %s"
            logger.exception(message)
        except requests.exceptions.ConnectionError:
            message = "Failed to connect to the API server"
            logger.exception(message)
        except requests.exceptions.Timeout:
            message = "Request timed out"
            logger.exception(message)
        except requests.exceptions.HTTPError:
            message = "HTTP error occurred"
            logger.exception(message)
        except requests.exceptions.RequestException:
            message = "Request failed"
            logger.exception(message)
        except Exception:
            message = "Unexpected error"
            logger.exception(message)

        else:
            return response

    def send_association(
        self,
        endpoint: str,
        idp: str,
        associations: list[AssociationUpdate] | None = None,
        headers: dict[str, str] | None = None,
    ) -> APIResponse:
        """
        Send an association to the API endpoint
        """

        # Validate endpoint
        if not endpoint:
            message = "Endpoint cannot be empty"
            raise ValueError(message)

        assoc_dict = {
            "associations": [
                association.model_dump() for association in associations
            ]
        }

        # Create and validate payload
        try:
            payload = AssociationsPayload(idp=idp, associations=assoc_dict)
        except ValueError:
            message = "Payload validation failed"
            logger.exception(message)
            raise

        # Prepare request
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if headers:
            default_headers.update(headers)

        try:
            # Log the request
            logger.info("Sending POST request to %s", url)
            logger.debug("Payload: %s", payload.model_dump_json(indent=2))

            # Send request
            response = self.session.post(
                url,
                json=payload.dict(),
                headers=default_headers,
                timeout=self.timeout,
                verify=False,  # we don't want to validate certs when testing
            )

            # Check for HTTP errors
            response.raise_for_status()

            # Parse response
            try:
                response_data = response.json()
                message = f"Request successful. Status: {response.status_code}"
                logger.info(message)
                return APIResponse(
                    status_code=response.status_code, data=response_data
                )
            except json.JSONDecodeError:
                message = "Failed to parse response JSON"
                logger.exception(message)
                return APIResponse(
                    status_code=response.status_code,
                    raw_response=response.text,
                )

        except requests.exceptions.ConnectionError:
            message = "Connection error"
            logger.exception(message)
            raise
        except requests.exceptions.Timeout:
            message = "Request timed out"
            logger.exception(message)
            raise
        except requests.exceptions.HTTPError:
            message = "HTTP error"
            logger.exception(message)
            raise
        except requests.exceptions.RequestException:
            message = "Request failed"
            logger.exception(message)
            raise
        except Exception:
            message = "Unexpected error"
            logger.exception(message)
            raise

    def send_updates(
        self,
        endpoint: str,
        idp: str,
        users: list[UserUpdate] | None = None,
        groups: list[GroupUpdate] | None = None,
        headers: dict[str, str] | None = None,
    ) -> APIResponse:
        """
        Send updates to the API endpoint.

        Args:
            endpoint: API endpoint path
            idp: Identity provider
            users: List of user updates
            groups: List of group updates
            headers: Optional headers to include in the request

        Returns:
            APIResponse object containing the response data

        Raises:
            ValueError: If input validation fails
            requests.exceptions.ConnectionError: If connection fails
            requests.exceptions.Timeout: If request times out
            requests.exceptions.HTTPError: If HTTP error occurs
            requests.exceptions.RequestException: For other request errors
        """
        # Validate endpoint
        if not endpoint:
            message = "Endpoint cannot be empty"
            raise ValueError(message)

        updates_dict = self.build_updates(groups, users)

        # Create and validate payload
        try:
            payload = UpdatePayload(idp=idp, updates=updates_dict)
        except ValueError:
            message = "Payload validation failed"
            logger.exception(message)
            raise

        # Prepare request
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if headers:
            default_headers.update(headers)

        try:
            # Log the request
            logger.info("Sending POST request to %s", url)
            logger.debug("Payload: %s", payload.model_dump_json(indent=2))

            # Send request
            response = self.session.post(
                url,
                json=payload.dict(),
                headers=default_headers,
                timeout=self.timeout,
                verify=False,  # we don't want to validate certs when testing
            )

            # Check for HTTP errors
            response.raise_for_status()

            # Parse response
            try:
                response_data = response.json()
                message = f"Request successful. Status: {response.status_code}"
                logger.info(message)
                return APIResponse(
                    status_code=response.status_code, data=response_data
                )
            except json.JSONDecodeError:
                message = "Failed to parse response JSON"
                logger.exception(message)
                return APIResponse(
                    status_code=response.status_code,
                    raw_response=response.text,
                )

        except requests.exceptions.ConnectionError:
            message = "Connection error"
            logger.exception(message)
            raise
        except requests.exceptions.Timeout:
            message = "Request timed out"
            logger.exception(message)
            raise
        except requests.exceptions.HTTPError:
            message = "HTTP error"
            logger.exception(message)
            raise
        except requests.exceptions.RequestException:
            message = "Request failed"
            logger.exception(message)
            raise
        except Exception:
            message = "Unexpected error"
            logger.exception(message)
            raise

    def build_updates(self, groups, users):
        """
        Builds the updates dictionary for the API request.
        :param groups: the groups and their operations
        :param users: the users and their operations
        :return: the updates dictionary
        """
        updates_dict = {}
        if users:
            updates_dict["users"] = [user.model_dump() for user in users]
        if groups:
            updates_dict["groups"] = [group.model_dump() for group in groups]
        return updates_dict


def send_webhook_updates(
    user_updates: list[UserUpdate] | None = None,
    group_updates: list[GroupUpdate] | None = None,
):
    """
    Send updates to the webhook endpoint.
    :param user_updates: the users and their operations
    :param group_updates: the groups and their operations
    :return: the API response
    """
    for base_endpoint in settings.WORKS_UPDATE_ENDPOINTS:
        config = APIClientConfig(
            base_url=base_endpoint,
            timeout=30,
            max_retries=3,
            backoff_factor=0.5,
        )
        client = APIClient(config)

        client.post_webhook(group_updates, user_updates)


def send_webhook_user_update(user_name: str):
    """
    Send updates to the webhook endpoint for one user.
    :param user_name: the user name to send an update for
    """
    user_updates = [
        UserUpdate(id=user_name, event=EventType.UPDATED),
    ]
    group_updates = []
    send_webhook_updates(user_updates, group_updates)
