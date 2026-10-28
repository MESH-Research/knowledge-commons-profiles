"""
Serve the country groups editorial document to the stats dashboard

The document lives in docs/ as markdown so that it can be read in the
repository; the dashboard shows the same file rendered to HTML, minus the
sections that only matter to maintainers.
"""

import re
from pathlib import Path

import bleach
import markdown

DOCUMENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "newprofile"
    / "country_groups_sources.md"
)

# Sections that are for maintainers rather than readers of the dashboard
HIDDEN_SECTIONS = ("Changing a group",)

ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "a",
    "em",
    "strong",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "br",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def strip_sections(markdown_text: str, headings: tuple[str, ...]) -> str:
    """
    Remove each named section, from its heading up to the next heading of
    the same or a higher level

    :param markdown_text: the document
    :param headings: heading texts (without the leading hashes) to remove
    :return: the document without those sections
    """
    kept = []
    skipping_level = None

    for line in markdown_text.splitlines(keepends=True):
        match = _HEADING.match(line)

        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            if skipping_level is not None and level <= skipping_level:
                skipping_level = None

            if skipping_level is None and title in headings:
                skipping_level = level

        if skipping_level is None:
            kept.append(line)

    return "".join(kept)


def load_document() -> str:
    """
    Read the document from docs/ with maintainer-only sections removed
    """
    return strip_sections(
        DOCUMENT_PATH.read_text(encoding="utf-8"), HIDDEN_SECTIONS
    )


def render_html(markdown_text: str) -> str:
    """
    Render markdown to sanitised HTML, with table support
    """
    html = markdown.markdown(markdown_text, extensions=["tables"])

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
