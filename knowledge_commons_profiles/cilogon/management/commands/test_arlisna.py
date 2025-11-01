"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.sync_apis.arlisna import ARLISNA
from knowledge_commons_profiles.cilogon.sync_apis.arlisna import (
    MembersSearchResponse,
)
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to test the MLA API
    """

    help = "Test the ARLISNA API"

    def handle(self, *args, **options):
        # cache.clear()
        # user = Profile.objects.get(username="pierrelandry")
        user = Profile.objects.get(username="kfitz")
        arlisna = ARLISNA()

        email_list = [user.email, *user.emails]

        logger.info("Searching for: %s", email_list)
        response: MembersSearchResponse = arlisna.search_multiple(email_list)

        self.check_result(arlisna, response["ARLISNA"], user)

        # check the comanage roles
        roles = Role.objects.filter(person__user__username=user.username)

        role: Role
        for role in roles:
            if role.organization is not None:
                logger.info(role)

        logger.info(user.is_member_of)

    def check_result(
        self,
        arlisna: ARLISNA,
        response: MembersSearchResponse,
        user: Profile,
    ):
        if response and response.TotalCount > 0:
            arlisna_id = response.Results[0]

            msg = (
                f"ARLISNA membership: "
                f"[{"active" if arlisna.is_member(arlisna_id.Email)
                else "inactive"}]"
            )

            logging.info(msg)
            return True
        logger.info("No account found on ARLISNA server")
        return False
