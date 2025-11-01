"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.sync_apis.msu import MSU
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role


class Command(BaseCommand):
    """
    Command to test the MLA API
    """

    help = "Test the MSU API"

    def handle(self, *args, **options):
        # cache.clear()
        user = Profile.objects.get(username="kfitz")
        msu = MSU()

        email_list = [user.email, *user.emails]

        logging.info("Searching for: %s", email_list)
        response: dict = msu.search_multiple(email_list)

        self.check_result(msu, response, user)

        # check the comanage roles
        roles = Role.objects.filter(person__user__username=user.username)

        role: Role
        for role in roles:
            if role.organization is not None:
                logging.info(role)

        logging.info(user.is_member_of)

    def check_result(
        self,
        msu: MSU,
        response,
        user: Profile,
    ):
        if response["MSU"]:
            logging.info("MSU membership: active")
            return True

        logging.info("No account found on MSU server")
        return False
