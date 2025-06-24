"""
Send data to the WordPress update endpoint

"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge_commons_profiles.rest_api.idms_api import APIClient
from knowledge_commons_profiles.rest_api.idms_api import APIClientConfig
from knowledge_commons_profiles.rest_api.idms_api import EventType
from knowledge_commons_profiles.rest_api.idms_api import GroupUpdate
from knowledge_commons_profiles.rest_api.idms_api import UserUpdate

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to test the WordPress update endpoint
    """

    help = "Test the WordPress update endpoint"

    def handle(self, *args, **options):

        for base_endpoint in settings.WORKS_UPDATE_ENDPOINTS:

            config = APIClientConfig(
                base_url=base_endpoint,
                timeout=30,
                max_retries=3,
                backoff_factor=0.5,
            )
            client = APIClient(config)

            # Prepare updates using Pydantic models
            user_updates = [
                UserUpdate(id="myusername", event=EventType.UPDATED),
                UserUpdate(id="anotherusername", event=EventType.CREATED),
            ]

            group_updates = [
                GroupUpdate(id="1234", event=EventType.UPDATED),
            ]

            client.post_webhook(group_updates, user_updates)
