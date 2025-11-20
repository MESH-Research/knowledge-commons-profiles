"""
The CC Search API interactions
Documentation is here: https://github.com/MESH-Research/commons-connect/blob/main/cc-search/docs/rest.md
These functions allow us to interact with the OpenSearch instance via an API
"""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Literal

import requests
from django.conf import settings
from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import ValidationError

from knowledge_commons_profiles.newprofile.utils import get_profile_photo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class CCSearchResponse(BaseModel):
    id: str = Field(alias="_id")
    title: str
    primary_url: AnyHttpUrl


class CCSearchMessage(BaseModel):
    message: str


CCSearchResult = CCSearchResponse | CCSearchMessage


class CCSearchOwner(BaseModel):
    name: str
    username: str
    url: AnyHttpUrl | str


class CCSearchDocument(BaseModel):
    title: str
    description: str
    owner: CCSearchOwner
    primary_url: AnyHttpUrl | str
    other_urls: list[AnyHttpUrl] | list[str] = Field(default_factory=list)
    thumbnail_url: AnyHttpUrl | str | None = None
    modified_date: str
    created_date: str | None
    content_type: Literal["profile"] = "profile"
    network_node: str = "hc"


# ruff: noqa: PLR0913
def build_cc_search_document(
    *,
    full_name: str,
    username: str,
    about: str,
    profile_url: str,
    other_urls: Sequence[str],
    thumbnail_url: str | None,
    modified_dt: datetime | None = None,
    created_dt: datetime | None = None,
    network_node: str = "hc",
    cc_id,
) -> CCSearchDocument:
    """
    Build the CC search payload for a user profile as a validated
    Pydantic model.
    """
    if not cc_id:
        created_dt = datetime.now(tz=UTC)

    if modified_dt is None:
        modified_dt = datetime.now(tz=UTC)

    owner = CCSearchOwner(
        name=full_name,
        username=username,
        url=profile_url,
    )

    # title + description follow your example
    if not created_dt:
        return CCSearchDocument(
            title=full_name,
            description=about,
            owner=owner,
            primary_url=profile_url,
            other_urls=list(other_urls),
            thumbnail_url=thumbnail_url,
            modified_date=modified_dt.strftime("%Y-%m-%d"),
            created_date=None,
            content_type="profile",
            network_node=network_node,
        )
    return CCSearchDocument(
        title=full_name,
        description=about,
        owner=owner,
        primary_url=profile_url,
        other_urls=list(other_urls),
        thumbnail_url=thumbnail_url,
        modified_date=modified_dt.strftime("%Y-%m-%d"),
        created_date=created_dt.strftime("%Y-%m-%d"),
        content_type="profile",
        network_node=network_node,
    )


def send_cc_search_document(
    doc: CCSearchDocument,
    cc_document_id: str | None = None,
    timeout: float | None = None,
) -> CCSearchResponse | None:
    """
    Send the document to CC search.

    - If `cc_document_id` is provided, does PUT /documents/{id}
    - Otherwise does POST /documents

    Returns the parsed JSON response.
    """
    base_url = settings.CC_SEARCH_URL.rstrip("/")
    if cc_document_id:
        url = f"{base_url}/documents/{cc_document_id}"
        method = "PUT"
    else:
        url = f"{base_url}/documents"
        method = "POST"

    headers = {
        "Authorization": f"Bearer {settings.CC_SEARCH_ADMIN_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.info("Sending %s request to %s", method, url)

    payload = doc.model_dump(exclude_none=True)

    if timeout is None:
        timeout = settings.CC_SEARCH_TIMEOUT

    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Error calling CC search API (%s %s)", method, url)
        return None

    try:
        adapter = TypeAdapter(CCSearchResult)
        parsed = adapter.validate_python(resp.json())
    except ValidationError:
        logger.exception("Error calling CC search API (%s %s)", method, url)
        return None
    except ValueError:
        logger.exception(
            "Error converting CC search API response to JSON (%s %s)",
            method,
            url,
        )
        return None

    try:
        return parsed
    except ValueError:
        logger.exception("CC search API returned non-JSON response")
        return None


# Optional convenience function tying it all together with a Django profile
def index_profile_in_cc_search(profile: Profile) -> CCSearchResponse | None:
    """
    Indexes a Profile in the CC search index
    """
    try:
        doc = build_cc_search_document(
            full_name=profile.name,
            username=profile.username,
            about=getattr(profile, "about_user", "") or "",
            profile_url=f"https://profiles.hcommons.org/members/"
            f"{profile.username}",
            other_urls=[
                f"https://mla.hcommons.org/members/{profile.username}",
                f"https://ajs.hcommons.org/members/{profile.username}",
                f"https://aseees.hcommons.org/members/{profile.username}",
                f"https://caa.hcommons.org/members/{profile.username}",
                f"https://up.hcommons.org/members/{profile.username}",
                f"https://commons.msu.edu/members/{profile.username}",
                f"https://arlisna.hcommons.org/members/{profile.username}",
                f"https://sah.hcommons.org/members/{profile.username}",
                f"https://commonshub.org/members/{profile.username}",
                f"https://socsci.hcommons.org/members/{profile.username}",
                f"https://stem.hcommons.org/members/{profile.username}",
                f"https://hastac.hcommons.org/members/{profile.username}",
                f"https://stemedplus.hcommons.org/members/{profile.username}",
            ],
            thumbnail_url=get_profile_photo(profile),
            modified_dt=datetime.now(tz=UTC),
            network_node="hc",
            cc_id=profile.cc_id,
        )
    except ValidationError:
        logger.exception(
            "Invalid data when building CC search document for profile %s",
            profile,
        )
        raise

    response: CCSearchResult = send_cc_search_document(
        doc, cc_document_id=profile.cc_id
    )

    if isinstance(response, CCSearchResponse):
        profile.cc_search_id = response.id
        profile.save()

    return response
