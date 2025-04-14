from unittest.mock import MagicMock
from unittest.mock import patch

import django.test
from django.core.cache import cache
from django.test import override_settings

from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.newprofile.works import Creator
from knowledge_commons_profiles.newprofile.works import HiddenWorks
from knowledge_commons_profiles.newprofile.works import Metadata
from knowledge_commons_profiles.newprofile.works import OutputFormat
from knowledge_commons_profiles.newprofile.works import OutputType
from knowledge_commons_profiles.newprofile.works import PersonOrOrg
from knowledge_commons_profiles.newprofile.works import Pid
from knowledge_commons_profiles.newprofile.works import Record
from knowledge_commons_profiles.newprofile.works import ResourceType
from knowledge_commons_profiles.newprofile.works import ResourceTypeInLanguage
from knowledge_commons_profiles.newprofile.works import RoleInfo
from knowledge_commons_profiles.newprofile.works import WorksApiError
from knowledge_commons_profiles.newprofile.works import WorksDeposits


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
)
class TestWorksDeposits(django.test.TestCase):

    def setUp(self):
        self.user = "0000-0000-0000-0000"
        self.works_url = "https://mock.api"
        self.works_deposits = WorksDeposits(
            user=self.user, works_url=self.works_url
        )
        self.fake_record = Record(
            id="abc123",
            links={"latest_html": "https://example.com/record/abc123"},
            metadata=Metadata(
                title="A Great Paper",
                publication_date="2024-01-01",
                publisher="Science Press",
                resource_type=ResourceType(
                    id="article",
                    title=ResourceTypeInLanguage(en="Journal article"),
                ),
                creators=[
                    Creator(
                        person_or_org=PersonOrOrg(
                            type="personal", name="Doe, Jane"
                        ),
                        role=RoleInfo(id="author", title={"en": "Author"}),
                    )
                ],
            ),
            pids={"doi": Pid(identifier="10.1234/example-doi")},
            custom_fields=None,
        )

    @patch("knowledge_commons_profiles.newprofile.works.httpx.get")
    def test_get_works_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {"hits": [self.fake_record.model_dump()]}
        }
        mock_get.return_value = mock_response

        result = self.works_deposits.get_works()

        self.assertIsInstance(result, list)
        self.assertEqual(result[0].id, "abc123")

    @patch("knowledge_commons_profiles.newprofile.works.httpx.get")
    def test_get_works_http_error(self, mock_get):
        cache_key = f"hc-member-profiles-xprofile-works-json-{self.user}"
        cache.delete(cache_key, version=newprofile.__version__)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP error")
        mock_get.return_value = mock_response

        with self.assertRaises(WorksApiError):
            self.works_deposits.get_works()

    @patch("knowledge_commons_profiles.newprofile.works.httpx.get")
    def test_get_works_cache_hit(self, mock_get):
        cache_key = f"hc-member-profiles-xprofile-works-json-{self.user}"
        cache.set(cache_key, [self.fake_record], timeout=300)

        result = self.works_deposits.get_works()

        self.assertEqual(result, [self.fake_record])
        mock_get.assert_not_called()

    @patch("knowledge_commons_profiles.newprofile.works.httpx.get")
    def test_get_formatted_works_html_output(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {"hits": [self.fake_record.dict()]}
        }
        mock_get.return_value = mock_response

        result = self.works_deposits.get_formatted_works(
            output_type=OutputType.HTML,
            output_format=OutputFormat.JUST_OUTPUT,
            hidden_works=HiddenWorks.SHOW,
        )

        self.assertIsInstance(result, str)
        self.assertIn("<", result)
        self.assertIn(">", result)

    @patch("knowledge_commons_profiles.newprofile.works.httpx.get")
    def test_get_formatted_works_json_output(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {"hits": [self.fake_record.dict()]}
        }
        mock_get.return_value = mock_response

        result = self.works_deposits.get_formatted_works(
            output_type=OutputType.JSON,
            output_format=OutputFormat.RAW_OBJECTS,
            hidden_works=HiddenWorks.SHOW,
        )

        self.assertIsInstance(result, dict)
        for section in result.values():
            for item in section:
                self.assertIn("html", item)
                self.assertIn("work_obj", item)

    def test_format_date_parts(self):
        date_string = "2023-12-31"
        expected = {"date-parts": [[2023, 12, 31]]}
        result = self.works_deposits.format_date_parts(date_string)
        self.assertEqual(result, expected)

    def test_sort_and_group_works_by_type_with_no_profile(self):
        grouped = self.works_deposits.sort_and_group_works_by_type(
            [self.fake_record]
        )
        self.assertIn("Journal article", grouped)
        self.assertEqual(len(grouped["Journal article"]), 1)

    def test_sort_and_group_works_respects_visibility_flags(self):
        profile = MagicMock()
        profile.works_order = '["order-Journal article"]'
        profile.works_show = '{"show_works_Journal article": false}'
        profile.works_work_show = "{}"

        works = WorksDeposits(
            user=self.user, works_url=self.works_url, user_profile=profile
        )
        result = works.sort_and_group_works_by_type(
            [self.fake_record], hidden_works=HiddenWorks.HIDE
        )

        self.assertEqual(result["Journal article"], [])

    def test_sort_and_group_works_ignores_hidden_individual_works(self):
        profile = MagicMock()
        profile.works_order = '["order-Journal article"]'
        profile.works_show = "{}"
        profile.works_work_show = '{"show_works_work_abc123": false}'

        works = WorksDeposits(
            user=self.user, works_url=self.works_url, user_profile=profile
        )
        result = works.sort_and_group_works_by_type(
            [self.fake_record], hidden_works=HiddenWorks.HIDE
        )

        self.assertEqual(result["Journal article"], [])

    def test_format_date_parts_with_invalid_date(self):
        with self.assertRaises(ValueError):
            self.works_deposits.format_date_parts("invalid-date")

    def test_build_work_entry_with_malformed_name(self):
        malformed_creator = Creator(
            person_or_org=PersonOrOrg(type="personal", name="JustOneName"),
            role=RoleInfo(id="author", title={"en": "Author"}),
        )
        malformed_record = Record(
            id="bad123",
            links={"latest_html": "https://example.com/record/bad123"},
            metadata=Metadata(
                title="Broken Paper",
                publication_date="2024-01-01",
                publisher="Broken Press",
                resource_type=ResourceType(
                    id="article",
                    title=ResourceTypeInLanguage(en="Journal article"),
                ),
                creators=[malformed_creator],
            ),
            pids={},
            custom_fields=None,
        )
        entry = self.works_deposits.build_work_entry(malformed_record)
        self.assertIn("author", entry)
        self.assertEqual(entry["author"][0]["family"], "JustOneName")
        self.assertEqual(entry["author"][0]["given"], "")

    def test_format_style_with_invalid_style_path(self):
        with self.settings(CITATION_STYLES={"INVALID": "not/a/real/path.csl"}):
            grouped = self.works_deposits.sort_and_group_works_by_type(
                [self.fake_record]
            )
            with self.assertRaises(ValueError):
                self.works_deposits.format_style("INVALID", grouped)

    def test_missing_fields_in_record(self):
        incomplete_record = Record(
            id="noid",
            links={"latest_html": "https://example.com"},
            metadata=Metadata(
                title="Untitled",
                publication_date="2022-01-01",
                publisher="Unknown",
                resource_type=ResourceType(
                    id="unknown",
                    title=ResourceTypeInLanguage(en=None),
                ),
                creators=[],
            ),
            pids={},
            custom_fields=None,
        )
        entry = self.works_deposits.build_work_entry(incomplete_record)
        self.assertEqual(entry["type"], "document")  # default type fallback
        self.assertNotIn(
            "container-title", entry
        )  # optional field is excluded if None
