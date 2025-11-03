# Works api-interaction views
import json
import logging

import django.db
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.works import HiddenWorks

logger = logging.getLogger(__name__)


@login_required
@require_POST
def works_deposits_edit(request):
    """
    A view for logged-in users to edit their works.
    """

    logger.debug("Editing works for %s", request.user)

    # get id_reference_style from POST
    id_reference_style = request.POST.get("reference_style", "")

    user = Profile.objects.prefetch_related("academic_interests").get(
        username=request.user
    )

    works_headings: list = API(
        request,
        user.username,
        use_wordpress=False,
        create=False,
        works_citation_style=id_reference_style,
    ).works_types(hidden_works=HiddenWorks.SHOW)

    # contains keys such as "Show_Book section" with JavaScript booleans
    try:
        works_show_map = json.loads(user.works_show)
    except TypeError:
        works_show_map = {}

    # contains keys such as show_axde-4213 with JavaScript booleans
    try:
        works_work_show_map = json.loads(user.works_work_show)
    except TypeError:
        works_work_show_map = {}

    user.reference_style = id_reference_style
    user.save()

    return render(
        request,
        "newprofile/fragments/works_edit_fragment.html",
        {
            "username": user.username,
            "profile": user,
            "logged_in_user_is_profile": True,
            "works_headings_ordered": works_headings,
            "works_show_map": works_show_map,
            "works_work_show_map": works_work_show_map,
        },
    )


@login_required
@require_POST
def save_works_visibility(request):
    """
    Save the visibility of the user's Works headings via AJAX
    """

    logger.debug("Saving works visibility for %s", request.user)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)

        works_visibility = str(json.dumps(data.get("works_visibility", {})))

        # get a profile
        api = API(
            request, request.user.username, use_wordpress=True, create=False
        )

        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-"
            f"{request.user.username}"
        )

        cache.delete(cache_key, version=VERSION)

        api.profile.works_work_show = works_visibility
        api.profile.save()

        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-"
            f"{request.user.username}"
        )

        cache.delete(cache_key, version=VERSION)

        return JsonResponse({"success": True})

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for saving works visibility: %s", ex
        )
        return JsonResponse({"success": False, "error": str(ex)}, status=400)
    except Exception as e:  # noqa: BLE001
        # Log the error for debugging
        logging.warning("Error saving profile order: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_POST
def save_works_order(request):
    """
    Save the ordering of the user's Works via AJAX
    """

    logger.debug("Saving works order for %s", request.user)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)

        item_order = str(json.dumps(data.get("item_order", [])))
        items_checked = str(json.dumps(data.get("show_work_values", {})))

        # get a profile
        api = API(
            request, request.user.username, use_wordpress=True, create=False
        )

        api.profile.works_order = item_order
        api.profile.works_show = items_checked
        api.profile.save()

        cache_key = (
            f"hc-member-profiles-xprofile-works-deposits-"
            f"{request.user.username}"
        )

        cache.delete(cache_key, version=VERSION)

        return JsonResponse({"success": True})

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for saving works order: %s", ex
        )
        return JsonResponse({"success": False, "error": str(ex)}, status=400)
    except Exception as e:  # noqa: BLE001
        # Log the error for debugging
        logging.warning("Error saving profile order: %s", e)
        return JsonResponse({"success": False, "error": str(e)}, status=400)
