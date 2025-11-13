"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.rest_api.sync import ExternalSync


class Command(BaseCommand):
    """
    Command to test the MLA API
    """

    help = "Test the MLA API"

    def handle(self, *args, **options):
        # cache.clear()
        # user = Profile.objects.get(username="martin_eve")
        # user = Profile.objects.get(username="pierrelandry")
        user = Profile.objects.get(username=options["username"])

        ExternalSync.sync(user, cache=False)

        # check the comanage roles
        roles = Role.objects.filter(person__user__username=user.username)

        role: Role
        for role in roles:
            if role.organization is not None:
                logging.info(role)

        logging.info(user.get_external_memberships())

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
