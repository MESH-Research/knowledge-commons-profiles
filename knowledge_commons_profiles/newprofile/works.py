"""
Works field type.

"""

import json
import logging
from collections import defaultdict
from enum import Enum

# ruff: noqa: PLC0206
from pathlib import Path
from typing import Any

import altair as alt
import httpx
import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_fixed

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.citeproc import Citation
from knowledge_commons_profiles.citeproc import CitationItem
from knowledge_commons_profiles.citeproc import CitationStylesBibliography
from knowledge_commons_profiles.citeproc import CitationStylesStyle
from knowledge_commons_profiles.citeproc import formatter
from knowledge_commons_profiles.citeproc.source.json import CiteProcJSON
from knowledge_commons_profiles.newprofile import models
from knowledge_commons_profiles.newprofile.utils import get_visibilities
from knowledge_commons_profiles.newprofile.utils import hide_work

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 10
CACHE_TIMEOUT = 1800  # 30 minutes

HTTP_200_OK = 200

CSL_TYPES = {
    "Journal article": "article-journal",
    "Book": "book",
    "Book section": "chapter",
    "Conference paper": "paper-conference",
    "Magazine article": "article-magazine",
    "Newspaper article": "article-newspaper",
    "Thesis": "thesis",
    "Review": "review-book",
    "Blog post": "webpage",
}

PLURALS = {
    "Thesis": "theses",
}


class Imprint(BaseModel):
    """
    Imprint information
    """

    title: str | None = None
    isbn: str | None = None
    place: str | None = None
    pages: str | None = None


class Journal(BaseModel):
    """
    Journal information
    """

    title: str
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    issn: str | None = None


class Pid(BaseModel):
    """
    Pid
    """

    identifier: str


class CustomFields(BaseModel):
    """
    CustomFields
    """

    imprint: Imprint | None = Field(None, validation_alias="imprint:imprint")
    journal: Journal | None = Field(None, validation_alias="journal:journal")

    # Additional custom fields
    kcr_commons_domain: str | None = Field(
        None, validation_alias="kcr:commons_domain"
    )
    kcr_submitter_email: str | None = Field(
        None, validation_alias="kcr:submitter_email"
    )
    kcr_submitter_username: str | None = Field(
        None, validation_alias="kcr:submitter_username"
    )
    kcr_user_defined_tags: list[str] | None = Field(
        None, validation_alias="kcr:user_defined_tags"
    )


class ResourceTypeInLanguage(BaseModel):
    """
    ResourceTypeInLanguage
    """

    en: str | None


class ResourceType(BaseModel):
    """
    ResourceType
    """

    title: ResourceTypeInLanguage
    id: str


class Identifier(BaseModel):
    """
    Identifier
    """

    identifier: str
    scheme: str


class PersonOrOrg(BaseModel):
    """
    PersonOrOrg
    """

    type: str  # Usually "personal"
    name: str
    given_name: str | None = None
    family_name: str | None = None
    identifiers: list[Identifier] | None = None


class RoleInfo(BaseModel):
    """
    RoleInfo
    """

    id: str  # e.g., "author", "editor", "translator"
    title: dict[str, str]  # e.g., {"en": "Author"}


class Affiliation(BaseModel):
    """
    Affiliation
    """

    id: str | None = None
    name: str


class Creator(BaseModel):
    """
    Creator
    """

    person_or_org: PersonOrOrg
    role: RoleInfo
    affiliations: list[Affiliation] | None = None


class Metadata(BaseModel):
    """
    Metadata
    """

    title: str
    publication_date: str
    publisher: str
    resource_type: ResourceType
    creators: list[Creator]


class Record(BaseModel):
    """
    A record
    """

    id: str
    links: dict[str, HttpUrl]
    metadata: Metadata
    pids: dict[str, Pid]
    custom_fields: CustomFields | None


class Hitdict(BaseModel):
    """
    A dictionary of hits
    """

    hits: dict[str, list[Record] | int]


class WorksApiError(Exception):
    """
    Works API error
    """


class HiddenWorks(Enum):
    """
    HiddenWorks enum
    """

    SHOW = 1
    HIDE = 2


class OutputType(Enum):
    """
    OutputType enum
    """

    HTML = 1
    JSON = 2


class OutputFormat(Enum):
    """
    OutputFormat enum
    """

    RAW_OBJECTS = 1
    JUST_OUTPUT = 2


class WorksVisibility(Enum):
    """
    WorksVisibility enum
    """

    SHOW_WORKS = 1
    HEADINGS_ONLY = 2


class WorksDeposits:
    """Works class."""

    def __init__(
        self,
        user: str,
        works_url: str,
        user_profile: models.Profile | None = None,
    ):
        """Constructor."""
        self.user: str = user
        self.works_url: str = works_url
        self.user_profile: models.Profile = user_profile

    def get_works_for_backend_edit(
        self,
        hidden_works=HiddenWorks.SHOW,
        style="MLA",
    ):
        """
        Get works for editing in the backend
        """
        return self.get_formatted_works(
            style=style,
            hidden_works=hidden_works.SHOW,
            output_type=OutputType.JSON,
            output_format=OutputFormat.RAW_OBJECTS,
        )

    def _create_sorted_works_types_list(self, work_types, show_hidden=False):
        """
        Create the final sorted list of work types

        """
        # Start with ordered types from user profile that exist in work_types

    def format_date_parts(
        self, date_string: str
    ) -> dict[str, list[list[int]]]:
        """
        Format a date string to be used in a dictionary
        """
        return {
            "date-parts": [
                [int(date_val) for date_val in date_string.split("-")]
            ]
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(httpx.RequestError),
    )
    def get_works(self):
        """
        Get the works for a user from the API
        """
        cache_key = f"hc-member-profiles-xprofile-works-json-{self.user}"

        result = cache.get(cache_key, version=VERSION)

        if result:
            return result

        endpoint: str = (
            f"{self.works_url + "/api/records"}?q="
            f"metadata.creators.person_or_org."
            f"identifiers.identifier:{self.user}&"
            f"size=100"
        )

        logger.info("Fetching record from %s", endpoint)

        headers: dict = {
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; "
            "rv:134.0) Gecko/20100101 Firefox/134.0",
        }

        try:
            response = httpx.get(
                endpoint, timeout=HTTP_TIMEOUT, headers=headers
            )
            response.raise_for_status()

            validated = Hitdict(**response.json())

            try:
                cache.set(
                    key=cache_key,
                    value=validated.hits["hits"],
                    timeout=CACHE_TIMEOUT,
                    version=VERSION,
                )
            except Exception as e:
                msg = (
                    f"Unable to cache works for user: {self.user} "
                    f"because {e}"
                )
                logger.exception(msg)

            return validated.hits["hits"]

        except httpx.HTTPStatusError as e:
            logger.exception("HTTP error")
            raise WorksApiError from e
        except httpx.RequestError as e:
            logger.exception("Request error")
            raise WorksApiError from e
        except (ValidationError, ValueError) as e:
            logger.exception("Validation or JSON error")
            raise WorksApiError from e
        except Exception as e:
            logger.exception("Unknown error")
            raise WorksApiError from e

    def get_works_for_frontend_display(self, style="MLA"):
        """
        Get works for frontend display
        """
        return self.get_formatted_works(
            style=style,
            hidden_works=HiddenWorks.HIDE,
            output_format=OutputFormat.JUST_OUTPUT,
            output_type=OutputType.HTML,
        )

    def sort_and_group_works_by_type(
        self, works: list[Record], hidden_works: HiddenWorks = HiddenWorks.HIDE
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Sort and group works by type
        """

        works_by_type: dict[str, list[dict[str, Any]]] = {}
        work_types = {
            w.metadata.resource_type.title.en
            for w in works
            if w.metadata.resource_type.title.en
        }

        if self.user_profile and self.user_profile.works_order:
            ordered_types = json.loads(self.user_profile.works_order)
            ordered_types = [
                t.split("order-")[-1]
                for t in ordered_types
                if t.split("order-")[-1] in work_types
            ]

            # Add any remaining types that aren't already in ordered list
            unordered_types = [t for t in work_types if t not in ordered_types]
            ordered_types.extend(sorted(unordered_types))
        else:
            ordered_types = sorted(work_types)

        visibility, visibility_works = get_visibilities(self, hidden_works)

        for work in works:
            work_entry = self.build_work_entry(work)
            work_type = work_entry["original_type"]

            # hide works in hidden sections
            hide_heading, hide_individual_work = hide_work(
                work, work_type, hidden_works, visibility, visibility_works
            )

            if any([hide_heading, hide_individual_work]):
                continue

            if work_type not in works_by_type:
                works_by_type[work_type] = []

            works_by_type[work_type].append(work_entry)

        for entries in works_by_type.values():
            entries.sort(
                key=lambda x: x.get("issued", {}).get(
                    "date-parts", [["n.d."]]
                )[0][0],
                reverse=True,
            )

        # Ensure all ordered_types are in the result, even if empty
        return {t: works_by_type.get(t, []) for t in ordered_types}

    def format_style(
        self,
        style: str,
        works_by_type: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[str]]:
        """
        Format works by style
        """

        result: dict[str, list[str]] = {}

        style_file = settings.CITATION_STYLES.get(
            style, settings.CITATION_STYLES.get("MLA")
        )

        style_path = (
            Path(settings.BASE_DIR) / style_file
            if "styles" in style_file
            else Path(style_file)
        )

        for section, works in works_by_type.items():
            bib_source = CiteProcJSON(works)
            bib_style = CitationStylesStyle(
                str(style_path), validate=False, locale="en-US"
            )
            bibliography = CitationStylesBibliography(
                bib_style, bib_source, formatter.html
            )

            for work in works:
                bibliography.register(Citation([CitationItem(work["id"])]))

            result[section] = [
                str(entry) for entry in bibliography.bibliography()
            ]

        return result

    def render_html(self, styled_works: dict[str, list[str]]) -> str:
        return render_to_string(
            "newprofile/works.html", context={"works_links": styled_works}
        )

    def get_formatted_works(
        self,
        style: str = "MLA",
        hidden_works: HiddenWorks = HiddenWorks.HIDE,
        output_format: OutputFormat = OutputFormat.JUST_OUTPUT,
        output_type: OutputType = OutputType.HTML,
    ) -> str | list[dict[str, Any]] | dict[str, Any]:
        """
        Get formatted works
        :param style: the CSL stylesheet to use
        :param hidden_works: how to handle hidden works
        :param output_format: whether to return just the output or an html and
         work_obj key underneath
        :param output_type: the output type
        """

        works = self.get_works()

        if not works:
            logger.info("No works found for user: %s", self.user)
            return "" if output_format else []

        grouped_works = self.sort_and_group_works_by_type(
            works, hidden_works=hidden_works
        )

        styled = self.format_style(style, grouped_works)

        # remove headers if there are no works
        if hidden_works == HiddenWorks.HIDE:
            to_remove = []

            for section, works in styled.items():
                if len(works) == 0:
                    to_remove.append(section)

            for section in to_remove:
                del styled[section]

        if output_format == OutputFormat.RAW_OBJECTS:
            combined = {}
            for section, html_list in styled.items():
                combined[section] = []
                for html, obj in zip(
                    html_list, grouped_works[section], strict=False
                ):
                    combined[section].append({"html": html, "work_obj": obj})
            return combined

        if output_type == OutputType.HTML:
            return self.render_html(styled)

        return grouped_works

    def build_work_entry(self, work: Record) -> dict[str, Any | None]:
        """
        Build a work dictionary
        """
        work_type: str = work.metadata.resource_type.title.en or "Other"

        container_title = (
            work.custom_fields.journal.title
            if work.custom_fields and work.custom_fields.journal
            else (
                work.custom_fields.imprint.title
                if work.custom_fields and work.custom_fields.imprint
                else None
            )
        )

        result = {
            "title": work.metadata.title,
            "url": str(work.links.get("latest_html")),
            "publisher": work.metadata.publisher,
            "id": work.id,
            "issued": self.format_date_parts(work.metadata.publication_date),
            "container-title": container_title,
            "DOI": work.pids.get("doi", Pid(identifier="")).identifier,
            "type": CSL_TYPES.get(work_type, "document"),
            "original_type": work_type,
        }

        if result["container-title"] is None:
            del result["container-title"]

        for creator in work.metadata.creators:
            role = creator.role.id

            if role not in result:
                result[role] = []

            # try to assign names
            try:
                result[role].append(
                    {
                        "family": creator.person_or_org.name.split(", ")[0],
                        "given": creator.person_or_org.name.split(", ")[1],
                    }
                )
            except IndexError:
                logger.warning("Unable to parse creator name: %s", creator)
                result[role].append(
                    {"family": creator.person_or_org.name, "given": ""}
                )

        return result

    def get_vega_chart_json(
        self,
        hidden_works=HiddenWorks.HIDE,
    ):
        """
        Build a JSON Vega representation of Works
        :return: JSON string
        """

        # caches
        works = self.get_works()

        color_map = {}
        color_map_counter = 0
        color_list = settings.CHART_COLORS
        color_count = len(color_list)

        visibility, visibility_works = get_visibilities(self, hidden_works)

        # Nested defaultdicts to simplify initialization
        year_counts = defaultdict(lambda: defaultdict(int))

        for work in works:

            year = work.metadata.publication_date.split("-")[0]
            work_type = work.metadata.resource_type.title.en

            # hide works in hidden sections
            hide_heading, hide_individual_work = hide_work(
                work, work_type, hidden_works, visibility, visibility_works
            )

            if any([hide_heading, hide_individual_work]):
                continue

            # Count works by year and type
            year_counts[year][work_type] += 1

            # Assign color if not already assigned
            if work_type not in color_map:
                color_map[work_type] = color_list[color_map_counter]
                color_map_counter = (color_map_counter + 1) % color_count

        # Generate final results and lists
        results = [
            {
                "Year": year,
                "Work Type": work_type,
                "Publications": count,
                "Color": color_map[work_type],
            }
            for year, work_types in year_counts.items()
            for work_type, count in work_types.items()
        ]

        work_type_list = list(color_map.keys())
        color_list_extended = list(color_map.values())

        source = pd.DataFrame.from_dict(results)

        return (
            alt.Chart(
                source,
                width="container",
                height=300,
            )
            .mark_bar(size=25)
            .encode(
                x=alt.X("Year:T", scale=alt.Scale(padding=25)),
                y="sum(Publications)",
                color=alt.Color(
                    "Work Type",
                    scale=alt.Scale(
                        domain=sorted(work_type_list),
                        range=color_list_extended,
                    ),
                    legend=alt.Legend(title="Work Type"),
                ),
            )
        ).to_json()
