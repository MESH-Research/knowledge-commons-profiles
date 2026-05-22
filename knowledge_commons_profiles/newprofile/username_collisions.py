"""
Pure helpers for detecting and resolving case-insensitive ``Profile.username``
collisions.

These functions contain no database access so they can be unit-tested in
isolation. They are imported by both the ``resolve_username_case_collisions``
management command and the data migration that resolves collisions before the
``username`` column is converted to the case-insensitive ``citext`` type.

A "collision" is two or more usernames that are equal once lower-cased. Lower
casing (rather than ``str.casefold``) is used deliberately to match the folding
PostgreSQL's ``citext`` type applies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def find_collision_groups(
    rows: Iterable[tuple[int, str]],
) -> dict[str, list[tuple[int, str]]]:
    """Group rows that collide case-insensitively.

    Args:
        rows: an iterable of ``(id, username)`` pairs.

    Returns:
        A mapping of ``username.lower()`` to the list of ``(id, username)``
        pairs sharing that lower-cased form, restricted to groups with more
        than one member. Each list is sorted by ``id`` ascending.
    """
    by_lower: dict[str, list[tuple[int, str]]] = {}
    for profile_id, username in rows:
        by_lower.setdefault(username.lower(), []).append(
            (profile_id, username)
        )

    return {
        key: sorted(members, key=lambda row: row[0])
        for key, members in by_lower.items()
        if len(members) > 1
    }


def next_free_suffixed_name(original: str, taken_lower: set[str]) -> str:
    """Return ``original`` with the smallest free numeric suffix appended.

    The suffix is appended to the original, case-preserving value, e.g.
    ``Alice`` -> ``Alice_1``. A candidate is "free" when its lower-cased form
    is not present in ``taken_lower``.

    Args:
        original: the username to suffix (original casing is preserved).
        taken_lower: lower-cased usernames that are already in use.

    Returns:
        ``f"{original}_{n}"`` for the smallest ``n >= 1`` whose lower-cased
        form is absent from ``taken_lower``.
    """
    suffix = 1
    while True:
        candidate = f"{original}_{suffix}"
        if candidate.lower() not in taken_lower:
            return candidate
        suffix += 1


def plan_renames(
    rows: Iterable[tuple[int, str]],
) -> list[tuple[int, str, str]]:
    """Plan the renames needed to remove every case-insensitive collision.

    For each collision group the lowest-``id`` (oldest) profile keeps its
    username unchanged; the remaining profiles are renamed with a numeric
    suffix. A newly assigned name never collides case-insensitively with any
    existing username or with another name assigned in the same plan.

    Args:
        rows: an iterable of ``(id, username)`` pairs covering every profile.

    Returns:
        An ordered list of ``(id, old_username, new_username)`` tuples, one per
        profile that must be renamed. Empty when there are no collisions.
    """
    rows = list(rows)
    groups = find_collision_groups(rows)

    # Seed with every existing username so a new name never collides with an
    # untouched profile; new names are added as they are assigned so two
    # renames in the same plan cannot claim the same suffix.
    taken_lower = {username.lower() for _id, username in rows}

    plan: list[tuple[int, str, str]] = []
    for key in sorted(groups):
        # The list is sorted by id; the first (oldest) profile is kept.
        for profile_id, username in groups[key][1:]:
            new_username = next_free_suffixed_name(username, taken_lower)
            taken_lower.add(new_username.lower())
            plan.append((profile_id, username, new_username))

    return plan
