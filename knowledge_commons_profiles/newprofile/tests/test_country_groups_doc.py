"""
Tests for serving the country groups editorial document on the dashboard
"""

import base64
from unittest.mock import patch

from django.test import SimpleTestCase
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.newprofile import country_groups_doc

DOC_MODULE = "knowledge_commons_profiles.newprofile.country_groups_doc"
STATS_VIEWS = "knowledge_commons_profiles.newprofile.views.stats"

STATS_CREDENTIALS = ("stats", "pw")

SAMPLE = """# Country Groups

> Intro note.

## What is being counted

Some *emphasis* here.

| Group | Basis |
| --- | --- |
| **Europe** | UN M49 |

### A nested section

Nested text.

## Changing a group

1. Edit the set.
2. Update the table.

## Aliases

| Alias | Group |
| --- | --- |
| EU | European Union |
"""


def _basic_auth_header() -> dict[str, str]:
    token = base64.b64encode(":".join(STATS_CREDENTIALS).encode()).decode()
    return {"authorization": f"Basic {token}"}


class StripSectionsTests(SimpleTestCase):
    """
    Named sections are removed up to the next heading of the same level
    """

    def test_removes_named_section_and_keeps_the_rest(self):
        result = country_groups_doc.strip_sections(
            SAMPLE, ("Changing a group",)
        )

        self.assertNotIn("Changing a group", result)
        self.assertNotIn("Edit the set", result)
        self.assertIn("## What is being counted", result)
        self.assertIn("## Aliases", result)
        self.assertIn("| EU | European Union |", result)

    def test_subsections_of_a_removed_section_go_too(self):
        text = (
            "# T\n\n## Changing a group\n\nx\n\n### Sub\n\ny\n\n## Next\n\nz\n"
        )

        result = country_groups_doc.strip_sections(text, ("Changing a group",))

        self.assertNotIn("### Sub", result)
        self.assertNotIn("y", result.replace("Changing", ""))
        self.assertIn("## Next", result)
        self.assertIn("z", result)

    def test_section_at_end_of_document_is_removed(self):
        text = "# T\n\n## Keep\n\nk\n\n## Changing a group\n\nx\n"

        result = country_groups_doc.strip_sections(text, ("Changing a group",))

        self.assertEqual(result.strip(), "# T\n\n## Keep\n\nk")

    def test_unknown_heading_leaves_text_unchanged(self):
        result = country_groups_doc.strip_sections(SAMPLE, ("Nope",))

        self.assertEqual(result, SAMPLE)


class LoadDocumentTests(SimpleTestCase):
    """
    The document is read from docs/ with maintainer sections removed
    """

    def test_reads_file_and_strips_hidden_sections(self):
        with patch(f"{DOC_MODULE}.DOCUMENT_PATH") as path:
            path.read_text.return_value = SAMPLE
            result = country_groups_doc.load_document()

        self.assertIn("# Country Groups", result)
        self.assertIn("## Aliases", result)
        self.assertNotIn("Changing a group", result)

    def test_real_document_loads_without_maintainer_section(self):
        result = country_groups_doc.load_document()

        self.assertIn("# Country Groups", result)
        self.assertNotIn("## Changing a group", result)


class RenderHtmlTests(SimpleTestCase):
    """
    Markdown is rendered to HTML, including tables, and kept safe
    """

    def test_renders_headings_emphasis_and_tables(self):
        html = country_groups_doc.render_html(SAMPLE)

        self.assertIn("<h1>Country Groups</h1>", html)
        self.assertIn("<h2>What is being counted</h2>", html)
        self.assertIn("<em>emphasis</em>", html)
        self.assertIn("<table>", html)
        self.assertIn("<th>Group</th>", html)
        self.assertIn("<strong>Europe</strong>", html)
        self.assertIn("<blockquote>", html)

    def test_strips_raw_html_and_scripts(self):
        html = country_groups_doc.render_html(
            "# T\n\n<script>alert(1)</script>\n\n<b onclick='x'>hi</b>\n"
        )

        self.assertNotIn("<script", html)
        self.assertNotIn("onclick", html)


@override_settings(BASICAUTH_USERS=dict([STATS_CREDENTIALS]))
class CountryGroupsDocViewTests(SimpleTestCase):
    """
    The dashboard can fetch the document as HTML or download it as markdown
    """

    def test_html_view_requires_basic_auth(self):
        response = self.client.get(reverse("stats_country_groups_doc"))

        self.assertEqual(response.status_code, 401)

    def test_html_view_renders_document_without_hidden_section(self):
        with patch(f"{DOC_MODULE}.DOCUMENT_PATH") as path:
            path.read_text.return_value = SAMPLE
            response = self.client.get(
                reverse("stats_country_groups_doc"),
                headers=_basic_auth_header(),
            )

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("<h2>What is being counted</h2>", content)
        self.assertIn("<table>", content)
        self.assertNotIn("Changing a group", content)

    def test_download_requires_basic_auth(self):
        response = self.client.get(reverse("stats_country_groups_doc_download"))

        self.assertEqual(response.status_code, 401)

    def test_download_serves_markdown_attachment_without_hidden_section(
        self,
    ):
        with patch(f"{DOC_MODULE}.DOCUMENT_PATH") as path:
            path.read_text.return_value = SAMPLE
            response = self.client.get(
                reverse("stats_country_groups_doc_download"),
                headers=_basic_auth_header(),
            )

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".md", response["Content-Disposition"])
        self.assertIn("## Aliases", content)
        self.assertNotIn("Changing a group", content)
