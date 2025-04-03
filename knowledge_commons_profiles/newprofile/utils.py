"""
Utility functions
"""

import logging

from django.db import OperationalError

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


def profile_exists_or_has_been_created(user):
    """
    Check if a user profile exists or, if not, if we can create one
    """
    # first we need to check if we have a user
    # use filter().first() to return None if no user for easier readability
    # than catching Profile.DoesNotExist
    profile_obj = Profile.objects.filter(username=user).first()

    if profile_obj is None:
        # now check if there's a WordPress user
        try:
            wp_user_obj = WpUser.objects.filter(user_login=user).first()

            if wp_user_obj:
                # if here, there is a WpUser but no Profile object, so
                # we need to create one
                try:
                    Profile.objects.create(username=wp_user_obj.user_login)
                except OperationalError:
                    # for some reason we can't create a Profile object
                    logger.warning(
                        "Unable to connect to MySQL database to create Profile"
                    )
                    raise
            else:
                return False

        except OperationalError:
            # if there's no WordPress database access, return False
            return False

    return True
