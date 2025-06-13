"""
Classes for syncing external data
"""

import json

from django.conf import settings

from knowledge_commons_profiles.cilogon.sync_apis import mla
from knowledge_commons_profiles.cilogon.sync_apis.sync_class import SyncClass
from knowledge_commons_profiles.common.profiles_email import (
    sanitize_email_for_dev,
)
from knowledge_commons_profiles.newprofile import models

CLASS_LOOKUPS: dict[str, SyncClass] = {"MLA": mla.MLA()}


class ExternalSync:
    """
    Base class for syncing external data
    """

    @staticmethod
    def sync(profile: models.Profile, class_list: list[str] | None = None):
        """
        Sync external data
        """

        class_list = (
            class_list if class_list else settings.EXTERNAL_SYNC_CLASSES
        )

        if not isinstance(class_list, list):
            class_list = [class_list]

        for class_name in class_list:
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
                    # see whether we can find a sync ID for this user
                    search_by_email = class_to_use.search(
                        email=sanitize_email_for_dev(profile.email)
                    )

                    if search_by_email.meta.status == "success":
                        sync_id = search_by_email.data[0].search_results[0].id

                        # save the sync ID for future use
                        sync_ids[class_name] = sync_id
                    else:
                        # we can't find the user so move on
                        continue

                # so by this point, sync_id should be set, either by retrieval
                # or by search on the MLA API
                is_member_of[class_name] = class_to_use.is_member(sync_id)
                in_membership_groups[class_name] = class_to_use.groups(sync_id)

            finally:
                profile.external_sync_ids = json.dumps(sync_ids)
                profile.is_member_of = json.dumps(is_member_of)
                profile.in_membership_groups = json.dumps(in_membership_groups)
                profile.save()
