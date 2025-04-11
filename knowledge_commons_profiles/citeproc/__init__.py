import json
import os
from pathlib import Path

from . import formatter
from . import types

# ruff: noqa: F401, E402, I001

DATA_PATH = Path(Path(Path(__file__).parent.resolve()) / "data")

SCHEMA_PATH = (Path(DATA_PATH) / "schema") / "csl.rng"
LOCALES_PATH = Path(DATA_PATH) / "locales"
STYLES_PATH = Path(DATA_PATH) / "styles"


NAMES = [
    "author",
    "collection_editor",
    "composer",
    "container_author",
    "editor",
    "editorial_director",
    "illustrator",
    "interviewer",
    "original_author",
    "recipient",
    "translator",
]

DATES = [
    "accessed",
    "container",
    "event_date",
    "issued",
    "original_date",
    "submitted",
]

NUMBERS = [
    "chapter_number",
    "collection_number",
    "edition",
    "issue",
    "number",
    "number_of_pages",
    "number_of_volumes",
    "volume",
]

VARIABLES = [
    "abstract",
    "annote",
    "archive",
    "archive_location",
    "archive_place",
    "authority",
    "call_number",
    "citation_label",
    "citation_number",
    "collection_title",
    "container_title",
    "container_title_short",
    "dimensions",
    "DOI",
    "event",
    "event_place",
    "first_reference_note_number",
    "genre",
    "ISBN",
    "ISSN",
    "jurisdiction",
    "keyword",
    "language",
    "locator",
    "medium",
    "note",
    "original_publisher",
    "original_publisher_place",
    "original_title",
    "page",
    "page_first",
    "PMCID",
    "PMID",
    "publisher",
    "publisher_place",
    "references",
    "section",
    "source",
    "status",
    "title",
    "title_short",
    "URL",
    "version",
    "year_suffix",
    *NAMES,
    *DATES,
    *NUMBERS,
]

with (Path(LOCALES_PATH) / "locales.json").open(encoding="utf-8") as file:
    locales_json = json.load(file)
    PRIMARY_DIALECTS = locales_json["primary-dialects"]
    LANGUAGE_NAMES = locales_json["language-names"]


from knowledge_commons_profiles.citeproc import _version
from knowledge_commons_profiles.citeproc.frontend import (
    CitationStylesBibliography,
)
from knowledge_commons_profiles.citeproc.frontend import (
    CitationStylesStyle,
)
from knowledge_commons_profiles.citeproc.source import (
    Citation,
)
from knowledge_commons_profiles.citeproc.source import (
    CitationItem,
)
from knowledge_commons_profiles.citeproc.source import (
    Locator,
)

__version__ = _version.get_versions()["version"]
