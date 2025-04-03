"""
Works field type.

"""

import logging

import requests
from django.core.cache import cache
from django.template.loader import render_to_string

from knowledge_commons_profiles import newprofile

HTTP_200_OK = 200


class WorksDeposits:
    """Works field type."""

    name = "Works Deposits"
    accepts_null_value = True

    def __init__(self, user, works_url):
        """Constructor."""
        self.user = user
        self.works_url = works_url

    def display_filter(self):
        """Front-end display of user's works, ordered by date.

        :param mixed      field_value: Field value.
        :param string|int field_id:    ID of the field.
        :return: mixed
        """
        cache_key = f"hc-member-profiles-xprofile-works-deposits-{self.user}"

        html = cache.get(cache_key, version=newprofile.__version__)

        if html:
            return str(html)

        api_endpoint = self.works_url + "/api/records"
        endpoint = (
            f"{api_endpoint}?q=metadata.creators.person_or_org."
            f"identifiers.identifier:{self.user}&size=100"
        )

        logging.info("Requesting endpoint: %s", endpoint)

        try:
            headers = {
                "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; "
                "rv:134.0) Gecko/20100101 Firefox/134.0",
            }

            with requests.Session() as session:
                response = session.get(endpoint, headers=headers)
                if response.status_code != HTTP_200_OK:
                    logging.info(
                        "Request failed with status code: %s",
                        response.status_code,
                    )
                    response.raise_for_status()
                works = response.json()

        except requests.exceptions.RequestException:
            return ""

        if (
            not works
            or not works.get("hits")
            or not works.get("hits", {}).get("hits")
        ):
            logging.info("No works (hits key) found for user: %s", self.user)
            return ""

        works_links = {}

        for work in works.get("hits", {}).get("hits", []):
            work_final = {
                "title": work.get("metadata", {}).get("title"),
                "url": work.get("links", {}).get("latest_html"),
                "date": work.get("metadata", {}).get("publication_date"),
            }

            work_type = (
                work.get("metadata", {})
                .get("resource_type", {})
                .get("title", {})
                .get("en", "Other")
            )

            if work_type not in works_links:
                works_links[work_type] = []

            works_links[work_type].append(work_final)

        html = render_to_string(
            "newprofile/works.html",
            context={"works_links": works_links},
        )

        # Set cache asynchronously
        cache.set(cache_key, html, 1800, version=newprofile.__version__)

        return html
