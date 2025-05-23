"""
Store stats in the DB

"""

import logging

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.cilogon.sync_apis.mla import MLA
from knowledge_commons_profiles.cilogon.sync_apis.mla import SearchApiResponse


class Command(BaseCommand):
    """
    Command to test the MLA API
    """

    help = "Test the MLA API"

    def handle(self, *args, **options):
        mla = MLA()
        response: SearchApiResponse = mla.search("kfitz@kfitz.info")

        if (
            response.meta.status == "success"
            and response.data[0].total_num_results > 0
        ):
            mla_id = response.data[0].search_results[0].get_user_info

            logging.info(mla.is_member(mla_id))
