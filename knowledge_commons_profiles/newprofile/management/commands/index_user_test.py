"""
A management command to index a user in CC
"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.cc_search import (
    index_profile_in_cc_search,
)
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Index a user in CC"

    def handle(self, *args, **options):

        profile = Profile.objects.get(username="martin_eve2")

        parsed = index_profile_in_cc_search(profile)

        logger.info(parsed)
