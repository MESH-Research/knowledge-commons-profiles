"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.sync_apis.mla import MLA
from knowledge_commons_profiles.cilogon.sync_apis.mla import SearchApiResponse
from knowledge_commons_profiles.newprofile.models import Role


class Command(BaseCommand):
    """
    Command to test the MLA API
    """

    help = "Test the MLA API"

    def handle(self, *args, **options):
        # cache.clear()
        mla = MLA()
        response: SearchApiResponse = mla.search("kfitz@kfitz.info")

        if (
            response.meta.status == "success"
            and response.data[0].total_num_results > 0
        ):
            mla_id = response.data[0].search_results[0].id

            msg = (
                f"MLA membership: "
                f"[{"active" if mla.is_member(mla_id) else "inactive"}]"
            )

            logging.info(msg)

        # check the comanage roles
        roles = Role.objects.filter(person__user__username="kfitz")

        role: Role
        for role in roles:
            if role.organization is not None:
                logging.info(role)
