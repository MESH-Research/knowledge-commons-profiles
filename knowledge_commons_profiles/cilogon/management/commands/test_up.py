"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.sync_apis.up import UP
from knowledge_commons_profiles.cilogon.sync_apis.up import Contact
from knowledge_commons_profiles.cilogon.sync_apis.up import (
    SalesforceQueryResponse,
)
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to test the UP API
    """

    help = "Test the ARLISNA API"

    def handle(self, *args, **options):
        # cache.clear()
        user = Profile.objects.get(username="sineadneville")
        # user = Profile.objects.get(username="martin_eve")
        # user = Profile.objects.get(username="mtmurphy")
        up = UP()

        email_list = [user.email, *user.emails]

        logger.info("Searching for: %s", email_list)
        response: SalesforceQueryResponse = up.search_multiple(email_list)

        self.check_result(up, response["UP"], user)

        # check the comanage roles
        roles = Role.objects.filter(person__user__username=user.username)

        role: Role
        for role in roles:
            if role.organization is not None:
                logger.info(role)

        logger.info(user.is_member_of)

    def check_result(
        self,
        up: UP,
        response: SalesforceQueryResponse[Contact],
        user: Profile,
    ):
        if response and response.totalSize > 0:
            sync_id = up.get_sync_id(response)

            msg = (
                f"UP membership: "
                f"[{"active" if up.is_member(sync_id)
                else "inactive"}]"
            )

            logging.info(msg)
            return True
        logger.info("No account found on UP server")
        return False
