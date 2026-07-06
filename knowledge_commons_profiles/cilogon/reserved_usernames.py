"""
Reserved-username matching.

Staff manage a list of prohibited username terms in the Django admin (the
``ReservedUsername`` model). This module turns those simple, admin-friendly
terms into matches against a candidate username.

The rules an admin needs to understand are deliberately small:

1. Matching ignores **case**, **hyphens** and **underscores**. A single entry
   ``knowledgecommons`` therefore blocks ``knowledge_commons``,
   ``Knowledge-Commons``, ``knowledgeCommons`` and so on.
2. A term blocks any username that **begins with** it. ``admin`` blocks
   ``admin``, ``admin123`` and ``administrator`` -- but not ``badminton``.
   This means trailing junk (``knowledgecommons123``) is handled with no
   extra effort from the admin.
3. ``*`` is a wildcard meaning "any characters here". Use ``*word*`` to block a
   word appearing anywhere in the username (``*support*`` blocks
   ``techsupport`` and ``mysupportbot``).

No regular expressions are ever entered by hand: ``*`` is the only special
character.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.db import transaction

from knowledge_commons_profiles.cilogon.models import ReservedUsername

if TYPE_CHECKING:
    from collections.abc import Iterable

# Characters that admins should not have to worry about when writing a term.
# Both the term and the candidate username have these removed before matching,
# so separator permutations collapse to a single entry.
_IGNORED_CHARS = str.maketrans("", "", " -_")


def normalize(value: str) -> str:
    """Lower-case ``value`` and drop spaces, hyphens and underscores."""
    return (value or "").lower().translate(_IGNORED_CHARS)


def _pattern_to_regex(pattern: str) -> re.Pattern | None:
    """
    Compile a normalized admin term into a start-anchored regex.

    ``*`` becomes ``.*`` (any characters); every other character is treated
    literally. Returns ``None`` for an empty term so it never matches
    everything.
    """
    normalized = normalize(pattern)
    if not normalized:
        return None

    # Escape everything, then turn the (now escaped) wildcard back into ".*".
    # Anchoring only at the start gives a prefix match, so "admin" catches
    # "admin123" while a leading "*" lets an admin match anywhere.
    body = re.escape(normalized).replace(r"\*", ".*")
    return re.compile("^" + body)


def username_is_reserved(username: str, patterns: Iterable[str]) -> bool:
    """
    Return ``True`` if ``username`` matches any of ``patterns``.

    ``patterns`` are the raw admin-entered terms (optionally containing ``*``).
    """
    candidate = normalize(username)
    if not candidate:
        return False

    for pattern in patterns:
        regex = _pattern_to_regex(pattern)
        if regex is not None and regex.match(candidate):
            return True

    return False


def get_reserved_patterns() -> list[str]:
    """Return the active reserved patterns from the database."""
    return list(
        ReservedUsername.objects.filter(active=True).values_list(
            "pattern", flat=True
        )
    )


# ---------------------------------------------------------------------------
# Import / export
#
# Reserved terms are moved between environments as plain text so it can be a
# copy-and-paste exercise. The format is one term per line, optionally followed
# by " | note". Blank lines and lines beginning with "#" are ignored, so a
# pasted list can be annotated.
#
# Import is a full sync: whatever is pasted becomes the complete list, and any
# term not in the pasted text is removed.
# ---------------------------------------------------------------------------


def parse_reserved_terms(text: str) -> list[tuple[str, str]]:
    """
    Parse pasted text into ``(pattern, note)`` pairs.

    Blank lines and ``#`` comments are skipped; a later duplicate of a pattern
    overrides an earlier one.
    """
    # Preserve insertion order while letting a later line override an earlier
    # duplicate (dict keeps first-seen order but updates the value in place).
    terms: dict[str, str] = {}
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        pattern, sep, note = stripped.partition("|")
        pattern = pattern.strip()
        if not pattern:
            continue

        terms[pattern] = note.strip() if sep else ""

    return list(terms.items())


def serialize_reserved_terms(terms: Iterable[tuple[str, str]]) -> str:
    """
    Render ``(pattern, note)`` pairs as pasteable text.

    A term with a note becomes ``pattern | note``; without one it is just the
    pattern.
    """
    lines = [
        f"{pattern} | {note}" if note else pattern for pattern, note in terms
    ]
    return "\n".join(lines)


def import_terms(text: str) -> int:
    """
    Replace the entire reserved list with the pasted ``text``.

    Every existing term is removed and the pasted terms become the complete
    list. Returns the number of terms imported. The whole operation runs in a
    transaction, so a failure leaves the current list untouched.
    """
    parsed = parse_reserved_terms(text)

    with transaction.atomic():
        ReservedUsername.objects.all().delete()
        ReservedUsername.objects.bulk_create(
            ReservedUsername(pattern=pattern, note=note, active=True)
            for pattern, note in parsed
        )

    return len(parsed)
