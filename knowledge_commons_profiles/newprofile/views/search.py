import logging
import math
import time

import requests
from django.conf import settings
from django.shortcuts import render
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic.v1 import ValidationError
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
CC_API_TIMEOUT = getattr(settings, "CC_API_TIMEOUT", 5)

MAX_CONTENT_RETRIES = 3  # how many times to retry on JSON/value errors
BACKOFF_FACTOR = 0.5  # 0.5s, 1s, 2s ... between attempts


class Person(BaseModel):
    """Owner / contributor info."""

    name: str | None = None
    username: str | None = None
    url: str | None = None
    role: str | None = None
    network_node: str | None = None

    model_config = ConfigDict(extra="ignore")


class Hit(BaseModel):
    """One search result item."""

    internal_id: str = Field(alias="_internal_id")
    id: str = Field(alias="_id")

    title: str
    description: str | None = None

    owner: Person | None = None
    contributors: list[Person] | None = None

    primary_url: str | None = None
    other_urls: list[str] | None = None
    thumbnail_url: str | None = None

    # These vary in format, so keep them as strings
    publication_date: str | None = None
    modified_date: str | None = None

    content_type: str | None = None
    network_node: str | None = None

    # Only present for posts/discussions
    content: str | None = None

    model_config = ConfigDict(extra="ignore")


class SearchResponse(BaseModel):
    total: int
    page: int
    per_page: int
    request_id: str | None = None
    hits: list[Hit]

    model_config = ConfigDict(extra="ignore")


# --- Retry-enabled session ----------------------------------------------------


def _requests_session_with_retries() -> requests.Session:
    """
    Build a requests.Session that retries on transient network errors
    and on 5xx responses. Safe to reuse across calls.
    """
    session = requests.Session()

    retry_cfg = Retry(
        total=3,
        backoff_factor=0.5,  # exponential: 0.5, 1.0, 2.0 ...
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        raise_on_status=False,  # we handle errors ourselves
    )

    adapter = HTTPAdapter(max_retries=retry_cfg)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# module-level session (thread-safe)
_retry_session = _requests_session_with_retries()

# --- Helper parsing -----------------------------------------------------------


def _get_positive_int(
    request,
    key: str,
    default: int,
    min_value: int = 1,
    max_value: int | None = None,
) -> int:
    raw = request.GET.get(key, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default

    value = max(value, min_value)
    if max_value is not None and value > max_value:
        value = max_value
    return value


# --- API caller ---------------------------------------------------------------


def _call_cc_search_api(query: str, page: int, per_page: int) -> dict:
    """
    Perform CC API search with retries + robust fallback.
    Returns a normalised dict that the view can rely on.
    """
    for attempt in range(1, MAX_CONTENT_RETRIES + 1):
        url = settings.CC_SEARCH_URL.rstrip("/") + "/search"
        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
        }

        try:
            response = _retry_session.get(
                url, params=params, timeout=CC_API_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            _log_sleep_backoff(attempt, exc)
            continue  # 🔁 try again from the top of the loop

        try:
            data = response.json()

            if "error" in data:
                msg = "CC search API returned error"
                # ruff: noqa: TRY301
                raise ValueError(msg)

            result: SearchResponse = SearchResponse.model_validate(data)
        except ValidationError as exc:
            if attempt < MAX_CONTENT_RETRIES:
                _log_sleep_backoff(attempt, exc)
                continue  # 🔁 try again from the top of the loop
        except ValueError as exc:
            # JSON parse error or explicit API error
            if attempt < MAX_CONTENT_RETRIES:
                _log_sleep_backoff(attempt, exc)
                continue  # 🔁 try again from the top of the loop
        else:
            # the API returns either documents or user profiles in a
            # universal search
            # this means that the template needs to work out the TYPE of entity
            # there is a "content_type" that should help with this
            documents = result.hits
            total_count = result.total

            current_page = int(data.get("page", page) or page)
            per_page = int(data.get("per_page", per_page) or per_page)

            return {
                "documents": documents,
                "total_count": int(total_count),
                "current_page": current_page,
                "per_page": per_page,
            }

    # if we get here, retries were exceeded
    return {
        "documents": [],
        "total_count": 0,
        "current_page": page,
        "per_page": per_page,
        "error": "Maximum retries exceeded",
    }


def _log_sleep_backoff(
    attempt: int, exc: ValidationError | ValueError | RequestException
):
    logger.warning(
        "CC search API returned invalid JSON / "
        "error (attempt %s/%s), retrying...",
        attempt,
        MAX_CONTENT_RETRIES,
        exc_info=exc,
    )
    # simple exponential backoff
    sleep_for = BACKOFF_FACTOR * (2 ** (attempt - 1))
    time.sleep(sleep_for)


# --- Main view ----------------------------------------------------------------


def search(request):
    query = (request.GET.get("q") or "").strip()
    current_page = _get_positive_int(request, "page", default=1, min_value=1)
    per_page = _get_positive_int(
        request, "per_page", default=PAGE_SIZE, min_value=1, max_value=100
    )

    api_result = _call_cc_search_api(
        query=query, page=current_page, per_page=per_page
    )

    rows = api_result["documents"]
    total_count = api_result["total_count"]
    current_page = api_result["current_page"]
    per_page = api_result["per_page"]

    error = None
    if "error" in api_result:
        error = api_result["error"]

    page_count = (
        max(1, math.ceil(total_count / per_page)) if total_count else 1
    )

    # Clamp
    current_page = max(1, min(current_page, page_count))

    has_prev = current_page > 1
    has_next = current_page < page_count

    next_cursor = current_page + 1 if has_next else None
    prev_cursor = current_page - 1 if has_prev else None

    return render(
        request,
        "newprofile/search.html",
        {
            "documents": rows,
            "has_next": has_next,
            "has_prev": has_prev,
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
            "current_page": current_page,
            "page_count": page_count,
            "total_count": total_count,
            "page_size": per_page,
            "query": query,
            "start_item": (current_page - 1) * per_page + 1,
            "end_item": min(current_page * per_page, total_count),
            "error": error,
        },
    )
