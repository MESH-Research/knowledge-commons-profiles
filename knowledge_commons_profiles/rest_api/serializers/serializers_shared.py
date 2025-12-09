import logging

from django.contrib.auth.models import User

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api import utils

logger = logging.getLogger(__name__)


def get_is_superadmin(obj: Profile) -> bool:
    """Work out whether the user is a superadmin"""
    try:
        user_object: User = User.objects.get(username=obj.username)
    except User.DoesNotExist:
        return False

    return any([user_object.is_superuser, user_object.is_staff])


def get_first_name(obj):
    """
    Get the first name
    """
    return utils.get_first_name(obj, logger)


def get_last_name(obj):
    """
    Get the last name
    """
    return utils.get_last_name(obj, logger)
