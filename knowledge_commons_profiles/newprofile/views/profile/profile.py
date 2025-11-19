# profile views
# ruff: noqa: A005
import json
import logging

import django.db
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.cc_search import (
    index_profile_in_cc_search,
)
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import process_orders
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)
from knowledge_commons_profiles.rest_api.idms_api import (
    send_webhook_user_update,
)

logger = logging.getLogger(__name__)


def profile(request, user=""):
    """
    The main page of the site.

    This view renders the main page of the site.
    """
    logger.debug("Getting profile for %s", user)
    if not profile_exists_or_has_been_created(user):
        raise Http404

    try:
        api: API = API(request, user, use_wordpress=False, create=False)

        profile_obj: Profile = api.profile

        # if the logged-in user is the same as the requested profile they are
        # viewing, we should show the edit navigation
        logged_in_user_is_profile: bool = request.user.username == user

        left_order: list = (
            json.loads(profile_obj.left_order)
            if profile_obj.left_order
            else []
        )
        right_order: list = (
            json.loads(profile_obj.right_order)
            if profile_obj.right_order
            else []
        )

        left_order_final, right_order_final = process_orders(
            left_order, right_order
        )

        del left_order
        del right_order

        user = User.objects.filter(username=profile_obj.username).first()

        return render(
            request=request,
            context={
                "username": profile_obj.username,
                "logged_in_user_is_profile": logged_in_user_is_profile,
                "profile": profile_obj,
                "user": user,
                "left_order": left_order_final,
                "right_order": right_order_final,
                # "works_headings_ordered": works_headings,
                # "works_show_map": works_show_map,
                # "works_work_show_map": works_work_show_map,
            },
            template_name="newprofile/profile.html",
        )

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for main profile view: %s", ex
        )
        # Return a minimal profile view that will still load
        # The HTMX endpoints will handle their own failures gracefully
        return render(
            request=request,
            context={
                "username": "",
                "logged_in_user_is_profile": request.user.username == user,
                "profile": None,
                "left_order": [],
                "right_order": [],
                "database_error": True,  # Flag to indicate DB is down
            },
            template_name="newprofile/profile.html",
        )


@login_required
def my_profile(request):
    """
    A view for logged-in users to view their own profile page.

    If the user is logged in, this view will redirect them to the main page
    with their username as the user parameter.

    :param request: The request object.
    :type request: django.http.HttpRequest
    """
    logger.debug("Getting 'my profile' for %s", request.user)

    # we call with create because this user is logged in and needs a profile
    return profile(request, user=request.user.username)


@login_required
def edit_profile(request):
    """
    A view for logged-in users to edit their own profile page.

    If the request is a POST, validate the form data and save it to the
    database.  If the request is a GET, return a form page with the
    user's current data pre-filled in.

    :param request: The request object.
    :type request: django.http.HttpRequest
    :return: A rendered HTML template with a form.
    :rtype: django.http.HttpResponse
    """

    logger.debug("Editing profile for %s", request.user)

    user = Profile.objects.prefetch_related("academic_interests").get(
        username=request.user
    )

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()

            # now trigger the webhook that sends updates to the system

            # Prepare updates using Pydantic models and send an update command
            # to third-party systems via webhook
            send_webhook_user_update(user.username)

            # now send an update to the CC search client
            index_profile_in_cc_search(user)

            return redirect("profile", user=user.username)
    else:
        form = ProfileForm(instance=user)

    left_order = json.loads(user.left_order) if user.left_order else []
    right_order = json.loads(user.right_order) if user.right_order else []

    left_order_final, right_order_final = process_orders(
        left_order, right_order
    )

    del left_order
    del right_order

    return render(
        request,
        "newprofile/edit_profile.html",
        {
            "form": form,
            "username": user.username,
            "profile": user,
            "left_order": left_order_final,
            "right_order": right_order_final,
            "logged_in_user_is_profile": True,
        },
    )


@login_required
@require_POST
def save_profile_order(request, side):
    """
    Save the ordering of the user's profile via AJAX
    """

    logger.debug("Saving profile order for %s", request.user)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)
        item_order = str(json.dumps(data.get("item_order", [])))

        # get a profile
        api = API(
            request, request.user.username, use_wordpress=True, create=False
        )

        if side == "left":
            api.profile.left_order = item_order
        else:
            api.profile.right_order = item_order

        api.profile.save()

        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-"
            f"{request.user.username}"
        )

        cache.delete(cache_key, version=VERSION)

        return JsonResponse({"success": True})

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for saving profile order: %s", ex
        )
        return JsonResponse({"success": False, "error": str(ex)}, status=400)
    except Exception as e:  # noqa: BLE001
        # Log the error for debugging
        logging.warning("Error saving profile order: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)
