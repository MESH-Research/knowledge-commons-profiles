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
