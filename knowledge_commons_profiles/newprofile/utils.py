"""
Utility functions
"""

import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.db import OperationalError

from knowledge_commons_profiles.common.profiles_email import (
    sanitize_email_for_dev,
)
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


def get_on_disk_image(
    path_type: str, obj_id: int
) -> tuple[str | None, str | None]:
    avatars_image_path: str = settings.WP_MEDIA_ROOT

    thumb = None
    full = None

    image_path: Path = Path(avatars_image_path) / path_type / str(obj_id)

    if not image_path.exists():
        msg = f"Path {image_path!s} does not exist"
        logger.info(msg)
        return None, None

    # Look for image files in the cover-image directory
    for filename in image_path.iterdir():
        filename_plain = filename.name

        if str(filename_plain).endswith(
            ("bpthumb.jpg", "bpthumb.jpeg", "bpthumb.png"),
        ):
            thumb = filename_plain

        if str(filename_plain).endswith(
            ("bpfull.jpg", "bpfull.jpeg", "bpfull.png"),
        ):
            full = filename_plain

    if not thumb and not full:
        msg = f"No image files found: {image_path!s}"
        logger.info(msg)

    return thumb, full


def get_profile_photo(profile: Profile):
    """
    Return the path to the user's profile image
    :return:
    """

    # see if we have a local entry
    try:
        msg = f"Testing whether image is local for {profile.username}"
        logger.info(msg)

        if profile.profile_image.startswith("/media/") or (
            hasattr(settings, "AWS_STORAGE_BUCKET_NAME")
            and settings.AWS_STORAGE_BUCKET_NAME in profile.profile_image
        ):
            msg = f"Image for {profile.username} is local"
            logger.info(msg)
            return profile.profile_image
    except AttributeError:
        msg = f"Image for {profile.username} is not local (thrown)"
        logger.exception(msg)

    # see if we can find an image on disk, in the same way as BuddyPress
    thumb, full = profile.get_on_disk_profile_image()
    msg = (
        f"{profile.username} ({profile.central_user_id}) has an "
        f"image on disk: using this"
    )

    if full:
        logger.info(msg)
        return (
            settings.WP_MEDIA_URL
            + f"/avatars/{profile.central_user_id}/{full}"
        )
    if thumb:
        logger.info(msg)
        return (
            settings.WP_MEDIA_URL
            + f"/group-avatars/{profile.central_user_id}/{thumb}"
        )

    # fall back to the DB from import
    profile_image = profile.profileimage_set.first()
    if profile_image:
        msg = f"Image for {profile.username} has been imported from WordPress"
        logger.info(msg)

        return profile_image.full

    msg = f"Image for {profile.username} is Gravatar"
    logger.info(msg)

    # Fall back to Gravatar
    email = sanitize_email_for_dev(profile.email)

    size = 150

    # Encode the email to lowercase and then to bytes
    email_encoded = email.lower().encode("utf-8")

    # Generate the SHA256 hash of the email
    email_hash = hashlib.sha256(email_encoded).hexdigest()

    # Construct the URL with encoded query parameters
    query_params = urlencode({"s": str(size)})
    return f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"
