"""
Read-only preview of what an UP sync would change for a profile.

Everything here is pure computation over a profile plus the result of the
sync class's public methods; nothing is saved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus

if TYPE_CHECKING:
    from knowledge_commons_profiles.cilogon.sync_apis.sync_class import (
        SyncClass,
    )


@dataclass
class RoleChange:
    role_id: int
    organization: str
    current_status: str
    new_status: str

    @property
    def changed(self) -> bool:
        return self.current_status != self.new_status


@dataclass
class SyncPreview:
    username: str
    emails: list[str]
    sync_id: str | None
    is_member: bool
    groups: list[str]
    current_sync_id: str | None
    current_is_member: bool | None
    current_groups: list[str] | None
    role_changes: list[RoleChange] = field(default_factory=list)

    @property
    def would_change(self) -> bool:
        return (
            self.sync_id != self.current_sync_id
            or self.is_member != self.current_is_member
            or self.groups != self.current_groups
            or any(change.changed for change in self.role_changes)
        )


def _json_dict(value: str | None) -> dict:
    """Parse one of the profile's JSON text fields, tolerating junk."""
    if not value:
        return {}
    try:
        data = json.loads(value)
    except TypeError, json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def preview_sync(
    profile: Profile,
    sync_class: SyncClass,
    role_organizations: list[str],
    class_name: str = "UP",
) -> SyncPreview:
    """
    Compute what ``ExternalSync._sync_class`` would write for ``profile``
    using ``sync_class``, without writing anything.
    """
    emails = [e for e in [profile.email, *(profile.emails or [])] if e]

    found = sync_class.search_multiple(emails=emails)
    sync_id = sync_class.get_sync_id(found[class_name])

    if sync_id:
        is_member = bool(sync_class.is_member(sync_id))
        groups = list(sync_class.groups(sync_id))
    else:
        is_member = False
        groups = []

    new_status = RoleStatus.ACTIVE if is_member else RoleStatus.EXPIRED
    role_changes = [
        RoleChange(
            role_id=role.id,
            organization=role.organization,
            current_status=role.status,
            new_status=new_status,
        )
        for role in Role.objects.filter(person__user__username=profile.username)
        if role.organization in role_organizations
    ]

    return SyncPreview(
        username=profile.username,
        emails=emails,
        sync_id=sync_id,
        is_member=is_member,
        groups=groups,
        current_sync_id=_json_dict(profile.external_sync_ids).get(class_name),
        current_is_member=_json_dict(profile.is_member_of).get(class_name),
        current_groups=_json_dict(profile.in_membership_groups).get(class_name),
        role_changes=role_changes,
    )
