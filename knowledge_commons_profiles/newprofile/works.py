"""
Works field type.

"""

# ruff: noqa: PLC0206

import json
import logging

import requests
from django.core.cache import cache
from django.template.loader import render_to_string
from requests import Response

from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.newprofile import models

HTTP_200_OK = 200


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

    def get_headings(self, sort=False, show_works=False, show_hidden=False):
        """Get the headings for a user's Works."""
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
            self.get_works_list(
                final_sorted, works, works_links, show_hidden=show_hidden
            )

        return works_links

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
            work_final = {
                "title": work.get("metadata", {}).get("title"),
                "url": work.get("links", {}).get("latest_html"),
                "date": work.get("metadata", {}).get("publication_date"),
                "publisher": work.get("metadata", {}).get("publisher"),
                "id": work.get("id"),
            }

            work_type = (
                work.get("metadata", {})
                .get("resource_type", {})
                .get("title", {})
                .get("en", "Other")
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

    def get_works(self):
        """
        Get the works for a user from the API
        """
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
                return response.json()

        except requests.exceptions.RequestException:
            logging.exception("Error requesting Works endpoint: %s", endpoint)
            return None

    def display_filter(self):
        """Front-end display of user's works, ordered by date."""
        cache_key = f"hc-member-profiles-xprofile-works-deposits-{self.user}"

        html = cache.get(cache_key, version=newprofile.__version__)

        if html:
            return str(html)

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

        self.get_works_list(
            final_sorted, works, works_links, show_hidden=False
        )

        html = render_to_string(
            "newprofile/works.html",
            context={"works_links": works_links},
        )

        # Set cache asynchronously
        cache.set(cache_key, html, 1800, version=newprofile.__version__)

        return html
