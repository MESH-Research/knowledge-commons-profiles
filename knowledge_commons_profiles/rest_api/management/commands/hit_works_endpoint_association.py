"""
Send data to the WordPress update endpoint

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.oauth import send_association_message

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to test the WordPress update endpoint
    """

    help = "Test the WordPress update endpoint"

    def handle(self, *args, **options):

        send_association_message(
            sub="http://cilogon.org/serverE/users/329380", kc_id="martin_eve"
        )
