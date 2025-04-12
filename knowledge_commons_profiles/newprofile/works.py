"""
Works field type.

"""

import json
import logging

# ruff: noqa: PLC0206
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from requests import Response

from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.citeproc import Citation
from knowledge_commons_profiles.citeproc import CitationItem
from knowledge_commons_profiles.citeproc import CitationStylesBibliography
from knowledge_commons_profiles.citeproc import CitationStylesStyle
from knowledge_commons_profiles.citeproc import formatter
from knowledge_commons_profiles.citeproc.source.json import CiteProcJSON
from knowledge_commons_profiles.newprofile import models

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


class WorksDeposits:
    """Works field type."""

    name = "Works Deposits"
    accepts_null_value = True

    def __init__(
        self, user: str, works_url: str, user_profile: models.Profile = None
    ):
        """Constructor."""
        self.user: str = user
        self.works_url: str = works_url
        self.user_profile: models.Profile = user_profile

    def get_headings_and_works_for_edit(
        self, sort=False, show_works=False, show_hidden=False, style="MHRA"
    ):
        """Get the headings and works for a user's Works for editing."""
        works: dict = self.get_works()

        if (
            not works
            or not works.get("hits")
            or not works.get("hits", {}).get("hits")
        ):
            logging.info("No works (hits key) found for user: %s", self.user)
            return []

        work_types: list = list(
            {
                work.get("metadata", {})
                .get("resource_type", {})
                .get("title", {})
                .get("en", "Other")
                for work in works.get("hits", {}).get("hits", [])
            }
        )

        # sort the work types if the user requested it. Requires a Profile.
        if sort and self.user_profile and self.user_profile.works_order:
            final_sorted = self.create_final_sorted(
                work_types, show_hidden=True
            )
        else:
            final_sorted = work_types

        works_links: dict = {key: [] for key in final_sorted}

        # now add works if that has been requested
        if show_works:
            # list of dictionary objects
            works_links_citation = self.get_works_list(
                final_sorted, works, works_links, show_hidden=show_hidden
            )

            # dicts with lists of formatted html
            final_works: dict = self.format_style(
                style, works_links, works_links_citation
            )

            works_dict_final = {}
            item_counter = 0

            for section_counter, (section, works) in enumerate(
                final_works.items()
            ):
                works_dict_final[section] = []

                for work_html in works:
                    works_dict_final[section].append(
                        {
                            "html": work_html,
                            "work_obj": works_links_citation["items"][
                                section_counter
                            ][item_counter],
                        }
                    )
                    item_counter += 1

                item_counter = 0
        else:
            works_dict_final = works_links

        return works_dict_final

    def format_style(self, style, works_links, works_links_citation):
        final_works = {}
        work_index = 0
        keys = list(works_links.keys())

        style_file = settings.CITATION_STYLES.get(
            style, settings.CITATION_STYLES.get("MHRA")
        )

        # citeproc render each entry
        for list_of_works in works_links_citation.values():
            for citation_item in list_of_works:
                bib_source = CiteProcJSON(citation_item)

                bib_style = CitationStylesStyle(
                    str(
                        (Path(settings.STATIC_ROOT) / style_file)
                        if "styles" in style_file
                        else style_file
                    ),
                    validate=False,
                )
                bibliography = CitationStylesBibliography(
                    bib_style, bib_source, formatter.html
                )

                for citation in citation_item:
                    bibliography.register(
                        Citation([CitationItem(citation["id"])])
                    )

                # produces a list of list items. Need to join the inner lists
                final_bib = bibliography.bibliography()

                final_works[keys[work_index]] = final_bib
                work_index += 1

        return final_works

    def create_final_sorted(self, work_types, show_hidden=False):
        """
        Create the final sorted list of work types

        """
        # Start with ordered types from user profile that exist in work_types
        if self.user_profile and self.user_profile.works_order:
            ordered_types: list = json.loads(self.user_profile.works_order)
        else:
            ordered_types: list = []

        if (
            not show_hidden
            and self.user_profile
            and self.user_profile.works_show
        ):
            visibility_list = json.loads(self.user_profile.works_show)
        else:
            visibility_list = {}

        if show_hidden:
            # type names are stored in the database as order-<type_name>
            final_sorted = [
                type_name.split("order-")[1]
                for type_name in ordered_types
                if type_name.split("order-")[1] in work_types
            ]
            # Add any remaining types that weren't in the ordered list
            final_sorted.extend(
                [
                    type_name
                    for type_name in work_types
                    if type_name not in final_sorted
                ]
            )
        else:
            # type names are stored in the database as order-<type_name>
            final_sorted = [
                type_name.split("order-")[1]
                for type_name in ordered_types
                if type_name.split("order-")[1] in work_types
                and visibility_list.get(
                    "show_works_" + type_name.split("order-")[1], True
                )
            ]
            # Add any remaining types that weren't in the ordered list
            final_sorted.extend(
                [
                    type_name
                    for type_name in work_types
                    if type_name not in final_sorted
                    and visibility_list.get("show_works_" + type_name, True)
                ]
            )

        return final_sorted

    def format_date_for_dict(self, date_string):
        """
        Format a date string to be used in a dictionary
        :return:
        """
        # Split the date string by hyphens
        parts = date_string.split("-")

        # Create the nested structure
        result = {"date-parts": [[]]}

        # Add available parts to the inner list
        for part in parts:
            result["date-parts"][0].append(part)

        return result

    def get_works_list(
        self,
        final_sorted: list,
        works: dict,
        works_links: dict,
        show_hidden=False,
    ):
        """
        Add works to the prepopulated works_links dict
        """
        try:
            works_work_show = json.loads(self.user_profile.works_work_show)
        except (TypeError, AttributeError):
            works_work_show = {}

        for work in works.get("hits", {}).get("hits", []):
            work_final, work_type = self.build_work(work)

            for creator in work.get("metadata", {}).get("creators", {}):
                role = creator["role"]["id"]

                if role not in work_final:
                    work_final[role] = []

                # try to assign names
                try:
                    work_final[role].append(
                        {
                            "family": creator["person_or_org"]["name"].split(
                                ", "
                            )[0],
                            "given": creator["person_or_org"]["name"].split(
                                ", "
                            )[1],
                        }
                    )
                except IndexError:
                    logging.warning(
                        "Unable to parse creator name: %s", creator
                    )

            # if the section isn't visible or the work is hidden and
            # the show_hidden flag is true, then don't add the work
            if work_type not in final_sorted or (
                "show_works_work_" + work_final["id"] in works_work_show
                and works_work_show["show_works_work_" + work_final["id"]]
                is False
                and show_hidden is False
            ):
                # invisible
                continue
            works_links[work_type].append(work_final)

        for key in works_links:
            works_links[key].sort(
                key=lambda x: x["date"],
                reverse=True,
            )

        works_links_new = {"items": []}

        for value in works_links.values():
            works_links_new["items"].append(value)

        return works_links_new

    def build_work(self, work):
        """
        Build a work object
        """
        work_final = {
            "title": work.get("metadata", {}).get("title"),
            "url": work.get("links", {}).get("latest_html"),
            "date": work.get("metadata", {}).get("publication_date"),
            "publisher": work.get("metadata", {}).get("publisher"),
            "id": work.get("id"),
            "issued": self.format_date_for_dict(
                work.get("metadata", {}).get("publication_date")
            ),
        }
        work_type = (
            work.get("metadata", {})
            .get("resource_type", {})
            .get("title", {})
            .get("en", "Other")
        )
        work_final["original_type"] = work_type
        csl_type = CSL_TYPES.get(work_type, "document")
        if csl_type in {"article-journal", "review-book"}:
            work_final["container-title"] = (
                work.get("custom_fields", {})
                .get("journal:journal", {})
                .get("title", "")
            )
        if csl_type == "chapter":
            work_final["container-title"] = (
                work.get("custom_fields", {})
                .get("imprint:imprint", {})
                .get("title", "")
            )
        work_final["DOI"] = (
            work.get("pids", {}).get("doi", {}).get("identifier")
        )
        work_final["type"] = csl_type
        return work_final, work_type

    def get_works(self):
        """
        Get the works for a user from the API
        """
        cache_key = f"hc-member-profiles-xprofile-works-json-{self.user}"

        result = cache.get(cache_key, version=newprofile.__version__)

        if result:
            return result

        endpoint: str = (
            f"{self.works_url + "/api/records"}?q="
            f"metadata.creators.person_or_org."
            f"identifiers.identifier:{self.user}&"
            f"size=100"
        )

        logging.info("Requesting endpoint: %s", endpoint)

        try:
            headers: dict = {
                "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; "
                "rv:134.0) Gecko/20100101 Firefox/134.0",
            }

            with requests.Session() as session:
                response: Response = session.get(endpoint, headers=headers)
                if response.status_code != HTTP_200_OK:
                    logging.info(
                        "Request failed with status code: %s",
                        response.status_code,
                    )
                    response.raise_for_status()

                result = response.json()

                try:
                    cache.set(
                        cache_key,
                        result,
                        1800,
                        version=newprofile.__version__,
                    )
                except Exception as e:
                    msg = (
                        f"Unable to cache works for user: {self.user} "
                        f"because {e}"
                    )
                    logging.exception(msg)

                return result

        except requests.exceptions.RequestException:
            logging.exception("Error requesting Works endpoint: %s", endpoint)
            return None

    def display_filter(self, style="MHRA"):
        """Front-end display of user's works, ordered by date."""

        works: dict = self.get_works()

        if (
            not works
            or not works.get("hits")
            or not works.get("hits", {}).get("hits")
        ):
            logging.info("No works (hits key) found for user: %s", self.user)
            return ""

        work_types: list = list(
            {
                work.get("metadata", {})
                .get("resource_type", {})
                .get("title", {})
                .get("en", "Other")
                for work in works.get("hits", {}).get("hits", [])
            }
        )

        # type names are stored in the database as order-<type_name>
        final_sorted = self.create_final_sorted(work_types, show_hidden=False)

        works_links: dict = {key: [] for key in final_sorted}

        works_links_citation = self.get_works_list(
            final_sorted, works, works_links, show_hidden=False
        )

        final_works = self.format_style(
            style, works_links, works_links_citation
        )

        return render_to_string(
            "newprofile/works.html",
            context={"works_links": final_works},
        )
