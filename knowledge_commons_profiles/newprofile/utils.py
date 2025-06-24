"""
Utility functions
"""

import json
import logging

from django.conf import settings
from django.db import OperationalError

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)
# ruff: noqa: PLC0415


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


def process_orders(left_order, right_order):
    """
    Process the JSON of item ordering into a list of fields that can be
     used for ordering the fields on the profile page.
    """

    field_left = settings.PROFILE_FIELDS_LEFT
    field_right = settings.PROFILE_FIELDS_RIGHT

    left_order_final = []
    right_order_final = []

    left_order_final.extend(
        [
            item.replace("-", "_").replace("form", "edit").replace("_edit", "")
            for item in left_order
            if item.replace("-", "_")
            .replace("form", "edit")
            .replace("_edit", "")
            in field_left
        ]
    )

    # get the items left in the allowed list that are not in the left order
    # and append them here
    left_order_final.extend(
        [
            item.replace("-", "_").replace("form", "edit").replace("_edit", "")
            for item in field_left
            if item.replace("-", "_").replace("form", "edit")
            not in left_order_final
        ]
    )

    right_order_final.extend(
        [
            item.replace("-", "_").replace("form", "edit").replace("_edit", "")
            for item in right_order
            if item.replace("-", "_")
            .replace("form", "edit")
            .replace("_edit", "")
            in field_right
        ]
    )

    right_order_final.extend(
        [
            item.replace("-", "_").replace("form", "edit").replace("_edit", "")
            for item in field_right
            if item.replace("-", "_").replace("form", "edit")
            not in right_order_final
        ]
    )
    return left_order_final, right_order_final


def hide_work(work, work_type, hidden_works, visibility, visibility_works):
    """
    Determine if a work should be hidden
    :return: booleans tuple: first bool for heading, second for work
    """
    from knowledge_commons_profiles.newprofile.works import HiddenWorks

    hide_heading = False
    hide_individual_work = False

    if hidden_works == HiddenWorks.HIDE and not visibility.get(
        f"show_works_{work_type}", True
    ):
        hide_heading = True

    # hide works individually hidden
    if hidden_works == HiddenWorks.HIDE and not visibility_works.get(
        f"show_works_work_{work.id}", True
    ):
        hide_individual_work = True

    return hide_heading, hide_individual_work


def get_visibilities(works_object, hidden_works):
    """
    Get visibilities
    """

    from knowledge_commons_profiles.newprofile.works import HiddenWorks

    visibility: dict[str, bool] = {}
    visibility_works: dict[str, bool] = {}

    if (
        hidden_works == HiddenWorks.HIDE
        and works_object.user_profile
        and works_object.user_profile.works_show
    ):
        visibility = json.loads(works_object.user_profile.works_show)

    if (
        hidden_works == HiddenWorks.HIDE
        and works_object.user_profile
        and works_object.user_profile.works_work_show
    ):
        visibility_works = json.loads(
            works_object.user_profile.works_work_show
        )

    return visibility, visibility_works
