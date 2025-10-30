"""
Classes for syncing external data
"""

import json
import logging

from django.conf import settings

from knowledge_commons_profiles.cilogon.sync_apis import mla
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.newprofile import models
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus

CLASS_LOOKUPS: dict[str, SyncClass] = {"MLA": mla.MLA()}

logger = logging.getLogger(__name__)


class ExternalSync:
    """
    Base class for syncing external data
    """

    @staticmethod
    def sync(profile: models.Profile, class_list: list[str] | None = None):
        """
        Sync external data
        """

        logger.info("Syncing external data for %s", profile.username)

        class_list = (
            class_list if class_list else settings.EXTERNAL_SYNC_CLASSES
        )

        if not isinstance(class_list, list):
            class_list = [class_list]

        # ruff: noqa: B007
        for class_name, role_organization in class_list:
            class_to_use: SyncClass = CLASS_LOOKUPS[class_name]

            # see whether the Profile has an ID for this class
            sync_ids = json.loads(
                profile.external_sync_ids
                if profile.external_sync_ids
                else "{}"
            )

            is_member_of = json.loads(
                profile.is_member_of if profile.is_member_of else "{}"
            )

            in_membership_groups = json.loads(
                profile.in_membership_groups
                if profile.in_membership_groups
                else "{}"
            )

            try:
                sync_id = sync_ids.get(class_name, None)

                if not sync_id:
                    email_list = [profile.email, *profile.emails]

                    # see whether we can find a sync ID for this user
                    search_by_email = class_to_use.search_multiple(
                        emails=email_list
                    )

                    if search_by_email.meta.status == "success":
                        sync_id = search_by_email.data[0].search_results[0].id

                        # save the sync ID for future use
                        sync_ids[class_name] = sync_id
                    else:
                        # we can't find the user so move on
                        continue

                msg = (
                    f"Syncing {class_name} for {sync_id} on "
                    f"{profile.username}"
                )
                logger.info(msg)

                # so by this point, sync_id should be set, either by retrieval
                # or by search on the MLA API
                is_member_of[class_name] = class_to_use.is_member(sync_id)
                in_membership_groups[class_name] = class_to_use.groups(sync_id)

                # now update roles
                roles = Role.objects.filter(
                    person__user__username=profile.username
                )
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

            finally:
                profile.external_sync_ids = json.dumps(sync_ids)
                profile.is_member_of = json.dumps(is_member_of)
                profile.in_membership_groups = json.dumps(in_membership_groups)
                profile.save()
