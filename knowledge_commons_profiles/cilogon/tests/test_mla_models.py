"""
Tests for MLA pydantic model parsing against the shapes returned by the
v3 MLA API, which differ from the v2 shapes the models were first written
against (null membership fields and no addresses in search results; a
single publications_access object, a differently named publication
history key, no contributions history, nullable address types and an
is_primary_lang language flag in member detail results).
"""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from pydantic import TypeAdapter

from knowledge_commons_profiles.cilogon.sync_apis.mla import MLA
from knowledge_commons_profiles.cilogon.sync_apis.mla import MemberResponse
from knowledge_commons_profiles.cilogon.sync_apis.mla import (
    MemberResponseSuccess,
)
from knowledge_commons_profiles.cilogon.sync_apis.mla import SearchApiResponse
from knowledge_commons_profiles.cilogon.sync_apis.mla import (
    SimpleSuccessResponse,
)

SUCCESS_META = {"status": "success", "code": "API-1000", "message": ""}


def _v3_search_payload(**general_overrides) -> bytes:
    """A search result in the shape returned by the v3 API."""
    general = {
        "title": "Dr",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "suffix": None,
        "email": "ada@example.org",
        "email_visible": "N",
        "email_shareable": "",
        "phone": None,
        "web_site": None,
    }
    general.update(general_overrides)
    return json.dumps(
        {
            "meta": SUCCESS_META,
            "data": [
                {
                    "total_num_results": 1,
                    "search_results": [
                        {
                            "id": "12345",
                            "membership": {
                                "class_code": None,
                                "year_joined": None,
                                "membership_years": None,
                            },
                            "general": general,
                        }
                    ],
                }
            ],
        }
    ).encode()


def _v2_search_payload() -> bytes:
    """A search result in the older v2 shape, which must keep working."""
    return json.dumps(
        {
            "meta": SUCCESS_META,
            "data": [
                {
                    "total_num_results": 1,
                    "search_results": [
                        {
                            "id": "12345",
                            "membership": {
                                "class_code": "5",
                                "year_joined": "1999",
                                "membership_years": "20",
                            },
                            "general": {
                                "title": "Dr",
                                "first_name": "Ada",
                                "last_name": "Lovelace",
                                "suffix": None,
                                "email": "ada@example.org",
                                "email_visible": "Y",
                                "email_shareable": "",
                                "phone": "",
                                "web_site": "",
                                "addresses": [
                                    {
                                        "type": "home",
                                        "rank": None,
                                        "institution": None,
                                        "city": "London",
                                        "state": None,
                                        "zip": "N1",
                                        "country": "GB",
                                        "address1": "1 Example St",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()


def _v3_member_payload(expiring_date: str = "01/14/2028") -> bytes:
    """A member detail result in the shape returned by the v3 API."""
    return json.dumps(
        {
            "meta": SUCCESS_META,
            "data": [
                {
                    "id": "12345",
                    "authentication": {
                        "username": "ada",
                        "password": "$2a$10$notarealhash",
                        "membership_status": "active",
                    },
                    "membership": {
                        "class_code": "H",
                        "year_joined": "1995",
                        "membership_years": "32",
                        "starting_date": "01/15/2026",
                        "expiring_date": expiring_date,
                        "arb_status": "Cancelled",
                        "arb_bill_date": "01/09/2026",
                        "is_undergrad": "N",
                    },
                    "general": {
                        "title": "Dr",
                        "first_name": "Ada",
                        "last_name": "Lovelace",
                        "email": "ada@example.org",
                        "email_visible": "N",
                        "email_shareable": "",
                        "email_unsubscribe": "",
                        "online_newsletter": "",
                        "phone": None,
                        "website": None,
                        "joined_commons": "Y",
                        "donor_exclude": "",
                        "orcid": "0000-0000-0000-0000",
                        "new_mbr": "",
                        "mobile_phone": "",
                    },
                    "addresses": [
                        {
                            "id": "1",
                            "type": None,
                            "hidden": "",
                            "send_mail": "Y",
                            "line1": "1 Example St",
                            "line2": "",
                            "line3": "",
                            "city": "London",
                            "state": "",
                            "zip": "N1",
                            "country": "GB",
                            "country_code": "GB",
                            "department": "",
                            "department_other": "",
                        },
                        {
                            "id": "2",
                            "type": None,
                            "hidden": "",
                            "send_mail": "",
                            "affiliation": "Example University",
                            "ringgold_id": "1234",
                            "display_affil": "",
                            "department": "4360",
                            "other_dept": "",
                            "rank": "Professor",
                            "display_rank": "",
                            "line1": "2 Campus Rd",
                            "line2": "",
                            "line3": "",
                            "city": "London",
                            "state": "",
                            "zip": "N1",
                            "country": "GB",
                            "country_code": "GB",
                            "department_other": "",
                        },
                    ],
                    "publications_access": {
                        "type": "bulletins",
                        "access": {"ade": "N", "adfl": "N"},
                    },
                    "publication_history": [
                        {"year": "2009", "pub_code": "HB7"},
                        {"year": "2016", "pub_code": "HB8"},
                    ],
                    "organizations": [
                        {
                            "id": "74",
                            "name": "Digital Humanities",
                            "convention_code": "D046",
                            "position": "Member",
                            "type": "Forum",
                            "exclude_from_commons": "",
                            "primary": "Y",
                        },
                        {
                            "id": "161",
                            "name": "Nominating Committee",
                            "convention_code": "M029",
                            "position": "Member",
                            "type": "Committee",
                            "exclude_from_common": "",
                            "primary": "",
                        },
                    ],
                    "dues_history": [
                        {
                            "class_code": "15",
                            "name": "Joint Primary",
                            "starting_date": "01/15/2026",
                            "expiring_date": "01/14/2028",
                            "date_paid": "09/14/2026",
                            "dues_paid": "",
                            "joint_mem_id": "",
                            "joint_name": "",
                            "joint_sub_cls_code": "6",
                        }
                    ],
                    "languages": [
                        {"code": "2", "name": "French", "is_primary_lang": "Y"},
                        {"code": "3", "name": "Spanish", "is_primary_lang": ""},
                    ],
                    "pmla": {
                        "pmla_sub": "Y",
                        "end_date": "2028-01-14",
                        "may_renew_on": "2027-12-14",
                        "renewal_price": "12",
                    },
                    "time": {"authentication": 0.059, "tag": "membersearch"},
                }
            ],
        }
    ).encode()


class SearchResponseV3ParsingTests(SimpleTestCase):
    def test_v3_search_result_parses_as_success(self):
        result = TypeAdapter(SearchApiResponse).validate_json(
            _v3_search_payload()
        )

        self.assertIsInstance(result, SimpleSuccessResponse)
        self.assertEqual(result.data[0].total_num_results, 1)
        self.assertEqual(result.data[0].search_results[0].id, "12345")

    def test_v3_search_result_exposes_null_membership_fields(self):
        result = TypeAdapter(SearchApiResponse).validate_json(
            _v3_search_payload()
        )

        membership = result.data[0].search_results[0].membership
        self.assertIsNone(membership.class_code)
        self.assertIsNone(membership.year_joined)
        self.assertIsNone(membership.membership_years)

    def test_v3_search_result_without_addresses_has_empty_list(self):
        result = TypeAdapter(SearchApiResponse).validate_json(
            _v3_search_payload()
        )

        self.assertEqual(result.data[0].search_results[0].general.addresses, [])

    def test_v3_search_result_with_null_title_parses(self):
        result = TypeAdapter(SearchApiResponse).validate_json(
            _v3_search_payload(title=None)
        )

        self.assertIsInstance(result, SimpleSuccessResponse)
        self.assertIsNone(result.data[0].search_results[0].general.title)

    def test_v2_search_result_still_parses_as_success(self):
        result = TypeAdapter(SearchApiResponse).validate_json(
            _v2_search_payload()
        )

        self.assertIsInstance(result, SimpleSuccessResponse)
        general = result.data[0].search_results[0].general
        self.assertEqual(len(general.addresses), 1)
        self.assertEqual(general.addresses[0].city, "London")


class MemberResponseV3ParsingTests(SimpleTestCase):
    def test_v3_member_detail_parses_as_success(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        self.assertIsInstance(result, MemberResponseSuccess)
        self.assertEqual(result.data[0].id, "12345")
        self.assertEqual(result.data[0].membership.expiring_date, "01/14/2028")

    def test_v3_member_detail_null_address_type_parses(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        self.assertEqual(len(result.data[0].addresses), 2)
        self.assertIsNone(result.data[0].addresses[0].type)
        self.assertEqual(
            result.data[0].addresses[1].affiliation, "Example University"
        )

    def test_v3_member_detail_publication_history_parses(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        history = result.data[0].publication_history
        self.assertEqual([entry.pub_code for entry in history], ["HB7", "HB8"])

    def test_v3_member_detail_publications_access_object_parses(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        access = result.data[0].publications_access
        self.assertEqual(access.type, "bulletins")
        self.assertEqual(access.access["ade"], "N")

    def test_v3_member_detail_language_primary_flag_parses(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        languages = result.data[0].languages
        self.assertEqual(languages[0].name, "French")
        self.assertTrue(languages[0].is_primary)
        self.assertFalse(languages[1].is_primary)

    def test_v3_member_detail_organizations_parse(self):
        result = TypeAdapter(MemberResponse).validate_json(_v3_member_payload())

        names = [org.name for org in result.data[0].organizations]
        self.assertEqual(names, ["Digital Humanities", "Nominating Committee"])


class MLAClientV3BehaviourTests(SimpleTestCase):
    def test_is_member_true_for_v3_member_with_future_expiry(self):
        future = (datetime.now(tz=UTC) + timedelta(days=365)).strftime(
            "%m/%d/%Y"
        )
        with patch.object(
            MLA, "_query_mla_api", return_value=_v3_member_payload(future)
        ):
            self.assertTrue(MLA().is_member("12345"))

    def test_is_member_false_for_v3_member_with_past_expiry(self):
        past = (datetime.now(tz=UTC) - timedelta(days=365)).strftime("%m/%d/%Y")
        with patch.object(
            MLA, "_query_mla_api", return_value=_v3_member_payload(past)
        ):
            self.assertFalse(MLA().is_member("12345"))

    def test_search_multiple_finds_v3_search_result(self):
        with patch.object(
            MLA, "_query_mla_api", return_value=_v3_search_payload()
        ):
            result = MLA().search_multiple(["ada@example.org"])

        self.assertIsNotNone(result["MLA"])
        self.assertEqual(result["MLA"].data[0].search_results[0].id, "12345")

    def test_get_sync_id_from_v3_search_result(self):
        with patch.object(
            MLA, "_query_mla_api", return_value=_v3_search_payload()
        ):
            mla = MLA()
            result = mla.search_multiple(["ada@example.org"])

        self.assertEqual(mla.get_sync_id(result["MLA"]), "12345")
