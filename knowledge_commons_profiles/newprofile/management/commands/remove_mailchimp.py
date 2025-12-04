"""
A management command to test Mailchimp functions
"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_remove_user_from_mailchimp,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Test Mailchimp"

    def handle(self, *args, **options):

        logger.info("Testing Mailchimp...")

        hcommons_remove_user_from_mailchimp("martin_eve")

        logger.info("Mailchimp test done")
