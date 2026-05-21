"""
Classes for syncing external data
"""

import datetime
import json
import logging
from typing import Any

import requests
from django.conf import settings
from requests import RequestException

from knowledge_commons_profiles.cilogon.sync_apis import arlisna
from knowledge_commons_profiles.cilogon.sync_apis import mla
from knowledge_commons_profiles.cilogon.sync_apis import msu
from knowledge_commons_profiles.cilogon.sync_apis import up
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.newprofile import models
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus

CLASS_LOOKUPS: dict[str, SyncClass] = {
    "MLA": mla.MLA(),
    "MSU": msu.MSU(),
    "ARLISNA": arlisna.ARLISNA(),
    "UP": up.UP(),
}

logger = logging.getLogger(__name__)


class ExternalSync:
    """
    Base class for syncing external data
    """

    @staticmethod
    def sync(
        profile: models.Profile,
        class_list: list[str] | None = None,
        send_webhook=True,
        cache=True,
        webhooks=True,
    ) -> dict[str, bool]:
        """
        Sync external data
        """

        # don't sync if we've already done this in the period specified
        # in settings.SYNC_HOURS
        try:
            if (
                cache
                and profile.last_sync
                and (
                    datetime.datetime.now(tz=datetime.UTC) - profile.last_sync
                ).total_seconds()
                < settings.SYNC_HOURS * 60 * 60
            ):
                msg = (
                    f"External data sync is already synced for "
                    f"{profile.username}. Using cached version."
                )
                logger.info(msg)
                return profile.is_member_of
        except TypeError:
            msg = (
                f"Not caching external data sync for {profile.username} "
                f"due to an error."
            )
            logger.info(msg)

        logger.info("Syncing external data for %s", profile.username)

        class_list = (
            class_list if class_list else settings.EXTERNAL_SYNC_CLASSES
        )

        if not isinstance(class_list, list):
            class_list = [class_list]

        try:
            is_member_of = json.loads(
                profile.is_member_of if profile.is_member_of else "{}"
            )
        except TypeError:
            is_member_of = {}

        # ruff: noqa: B007
        for class_name, role_organization in class_list:
            class_to_use: SyncClass = CLASS_LOOKUPS[class_name]

            # see whether the Profile has an ID for this class
            sync_ids = json.loads(
                profile.external_sync_ids
                if profile.external_sync_ids
                else "{}"
            )

            in_membership_groups = json.loads(
                profile.in_membership_groups
                if profile.in_membership_groups
                else "{}"
            )

            try:
                ExternalSync._sync_class(
                    class_name,
                    class_to_use,
                    in_membership_groups,
                    is_member_of,
                    profile,
                    role_organization,
                    sync_ids,
                )

            finally:
                profile.external_sync_ids = json.dumps(sync_ids)
                profile.in_membership_groups = json.dumps(in_membership_groups)

        # now iterate over roles for known organizations
        ExternalSync._handle_comanage_roles(is_member_of, profile)

        profile.is_member_of = json.dumps(is_member_of)
        profile.last_sync = datetime.datetime.now(tz=datetime.UTC)
        profile.save()

        if webhooks:
            ExternalSync._send_webhooks(profile, send_webhook)

        logger.info("Roles are now %s", profile.is_member_of)

        return is_member_of

    @staticmethod
    def notify_subscribers(profile: Profile) -> None:
        """Ping ``settings.WEBHOOK_URLS`` so downstream services
        (BuddyPress) re-fetch this profile's memberships. Per-user signal
        — the webhook URL takes ``?username=…``, so the caller must fire
        it once per affected profile."""
        ExternalSync._send_webhooks(profile, send_webhook=True)

    @staticmethod
    def _send_webhooks(profile: Profile, send_webhook):
        if send_webhook:
            # send a ping to other services
            for url in settings.WEBHOOK_URLS:
                try:
                    requests.get(
                        url,
                        params={
                            "token": settings.WEBHOOK_TOKEN,
                            "username": profile.username,
                        },
                        timeout=8,  # 8 seconds to ping
                    )
                    msg = (
                        f"Webhook request update sent to {url} for "
                        f"user {profile.username}"
                    )
                    logger.info(msg)
                except (RequestException, TypeError):
                    logger.exception(
                        "Failed to send webhook to %s for user %s",
                        url,
                        profile.username,
                    )

    @staticmethod
    def refresh_local_memberships(profile: Profile) -> dict:
        """
        Refresh ``Profile.is_member_of`` from local ``Role`` rows only.

        Performs no external HTTP calls and does not bump ``last_sync``.
        Use after any path that writes ``Role`` rows locally (e.g. the
        ``import_comanage`` management command) so the cached membership
        JSON tracks the database without hammering external partner APIs.

        Existing keys in ``is_member_of`` for non-COmanage societies (e.g.
        MLA, MSU, ARLISNA, UP) are preserved; only the keys listed in
        ``settings.KNOWN_SOCIETY_MAPPINGS`` are recomputed from roles.
        """
        try:
            is_member_of = json.loads(profile.is_member_of or "{}")
        except (TypeError, json.JSONDecodeError):
            is_member_of = {}

        ExternalSync._handle_comanage_roles(is_member_of, profile)

        profile.is_member_of = json.dumps(is_member_of)
        profile.save(update_fields=["is_member_of"])

        return is_member_of

    @staticmethod
    def _handle_comanage_roles(
        is_member_of: dict[Any, Any] | Any, profile: Profile
    ):
        # names here correlate to the map in
        # humanities-commons/society-settings.php
        # the mapping configuration is in the base settings file.
        # role_overrides are deliberately NOT considered here:
        # is_member_of is the API/COmanage source of truth, role_overrides
        # is the manual layer, and the manage_roles UI separates them by
        # checking each membership against is_member_of vs role_overrides
        # — merging the two would collapse that distinction. The merge is
        # done at read time by rest_api.utils.get_external_memberships.
        roles = list(
            Role.objects.filter(person__user__username=profile.username)
        )
        for key, val in settings.KNOWN_SOCIETY_MAPPINGS.items():
            is_member_of[val] = any(
                role.organization
                and role.organization.lower() == key
                and role.affiliation == "member"
                for role in roles
            )

    # ruff: noqa: PLR0913
    @staticmethod
    def _sync_class(
        class_name,
        class_to_use: SyncClass,
        in_membership_groups,
        is_member_of: dict[Any, Any] | Any,
        profile: Profile,
        role_organization,
        sync_ids,
    ):
        sync_id = sync_ids.get(class_name, None)

        email_list = [profile.email, *profile.emails]

        # see whether we can find a sync ID for this user
        search_by_email = class_to_use.search_multiple(emails=email_list)

        sync_id = class_to_use.get_sync_id(search_by_email[class_name])

        # save the sync ID for future use
        sync_ids[class_name] = sync_id

        if sync_id:
            msg = f"Syncing {class_name} for {sync_id} on {profile.username}"
            logger.info(msg)

            is_member_of[class_name] = class_to_use.is_member(sync_id)
            in_membership_groups[class_name] = class_to_use.groups(sync_id)
        else:
            is_member_of[class_name] = False
            in_membership_groups[class_name] = []

        # now update roles
        roles = Role.objects.filter(person__user__username=profile.username)
        role: Role

        logger.info("Updating COmanage roles")
        for role in roles:
            if role.organization in role_organization:
                logger.info(
                    "Updating COmanage role: %s for %s",
                    role_organization,
                    profile,
                )
                role.status = (
                    RoleStatus.ACTIVE
                    if is_member_of[class_name]
                    else RoleStatus.EXPIRED
                )
                role.save()
