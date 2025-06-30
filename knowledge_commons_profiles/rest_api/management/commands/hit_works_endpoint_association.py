"""
Send data to the WordPress update endpoint

"""

import json
import logging

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge_commons_profiles.rest_api.idms_api import APIClient
from knowledge_commons_profiles.rest_api.idms_api import APIClientConfig
from knowledge_commons_profiles.rest_api.idms_api import AssociationUpdate
from knowledge_commons_profiles.rest_api.idms_api import EventType

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

            association_updates = [
                AssociationUpdate(
                    id="http://cilogon.org/serverE/users/329380",
                    kc_id="martin_eve",
                    event=EventType.ASSOCIATED,
                ),
            ]

            try:
                # Send updates
                response = client.send_association(
                    endpoint="/api/webhooks/user_data_update",
                    idp="cilogon",
                    associations=association_updates,
                    headers={
                        "Authorization": "Bearer " + settings.WEBHOOK_TOKEN,
                    },
                )

                if response.data:
                    message = "Success! Response: %s"
                    logger.info(message, json.dumps(response.data, indent=2))
                else:
                    message = "Success! Raw response: %s"
                    logger.info(message, response.raw_response)

            except ValueError:
                message = "Validation error: %s"
                logger.exception(message)
            except requests.exceptions.ConnectionError:
                message = "Failed to connect to the API server"
                logger.exception(message)
            except requests.exceptions.Timeout:
                message = "Request timed out"
                logger.exception(message)
            except requests.exceptions.HTTPError:
                message = "HTTP error occurred"
                logger.exception(message)
            except requests.exceptions.RequestException:
                message = "Request failed"
                logger.exception(message)
            except Exception:
                message = "Unexpected error"
                logger.exception(message)

            else:
                return

        return
