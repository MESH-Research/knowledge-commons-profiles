"""
The main views for the profile app
"""

import json
import logging

import django
import redis
from basicauth.decorators import basic_auth_required
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connections
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import UserStats
from knowledge_commons_profiles.newprofile.models import WpUser
from knowledge_commons_profiles.newprofile.utils import process_orders
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)
from knowledge_commons_profiles.newprofile.works import HiddenWorks
from knowledge_commons_profiles.rest_api.idms_api import (
    send_webhook_user_update,
)

logger = logging.getLogger(__name__)

REDIS_TEST_TIMEOUT_VALUE = 25


def profile_info(request, username):
    """
    Get profile info via HTMX
    """
    logger.debug("Getting profile info for %s", username)

    try:
        api = API(request, username, use_wordpress=False, create=False)

        context = {
            "profile_info": api.get_profile_info(),
            "academic_interests": api.get_academic_interests(),
            "education": api.get_education(),
            "about_user": api.get_about_user(),
            "show_education": api.profile.show_education,
            "show_publications": api.profile.show_publications,
            "show_projects": api.profile.show_projects,
            "show_academic_interests": api.profile.show_academic_interests,
        }

        return render(
            request, "newprofile/partials/profile_info.html", context
        )

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for profile info: %s", ex
        )
        # Return safe fallback context
        context = {
            "profile_info": {
                "name": "",
                "username": username,
                "profile": None,
            },
            "academic_interests": [],
            "education": "",
            "about_user": "",
            "show_education": False,
            "show_publications": False,
            "show_projects": False,
            "show_academic_interests": False,
        }
        return render(
            request, "newprofile/partials/profile_info.html", context
        )


def works_deposits(request, username, style=None):
    """
    Get profile info via HTMX
    """
    logger.debug("Getting works deposits for %s", username)

    try:
        api = API(
            request,
            username,
            use_wordpress=False,
            create=False,
            works_citation_style=style,
        )

        api.works_citation_style = (
            api.profile.reference_style if style is None else style
        )

        # Get the works deposits for this username
        user_works_deposits = api.works_html if api.profile.show_works else []

        return render(
            request,
            "newprofile/partials/works_deposits.html",
            {
                "works_headings_ordered": user_works_deposits,
                "works_html": user_works_deposits,
                "profile": api.profile,
                "show_works": api.profile.show_works,
                "chart": api.works_chart_json,
            },
        )

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for works deposits: %s", ex
        )
        # Return safe fallback context
        context = {
            "works_headings_ordered": [],
            "works_html": [],
            "profile": None,
            "show_works": False,
            "chart": "{}",
        }
        return render(
            request, "newprofile/partials/works_deposits.html", context
        )


def mastodon_feed(request, username):
    """
    Get a mastodon feed via HTMX
    """
    logger.debug("Getting mastodon feed for %s via HTMX", username)

    try:
        api = API(request, username, use_wordpress=False, create=False)

        profile_info_obj = api.get_profile_info()

        # Check for nocache parameter in querystring
        nocache = request.GET.get("nocache", "").lower() in ("true", "1", "yes")

        # Get the mastodon posts for this username
        user_mastodon_posts = (
            (
                api.mastodon_posts.latest_posts(nocache=nocache)
                if api.profile_info["mastodon"]
                else []
            )
            if profile_info_obj["profile"].show_mastodon_feed
            else []
        )

        return render(
            request,
            "newprofile/partials/mastodon_feed.html",
            {
                "mastodon_posts": user_mastodon_posts,
                "profile": profile_info_obj,
                "show_mastodon_feed": profile_info_obj[
                    "profile"
                ].show_mastodon_feed,
            },
        )

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for mastodon feed: %s", ex
        )
        # Return safe fallback context
        context = {
            "mastodon_posts": [],
            "profile": {"profile": None},
            "show_mastodon_feed": False,
        }
        return render(
            request, "newprofile/partials/mastodon_feed.html", context
        )


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

        return render(
            request=request,
            context={
                "username": user,
                "logged_in_user_is_profile": logged_in_user_is_profile,
                "profile": profile_obj,
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
                "username": user,
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


def blog_posts(request, username):
    """
    Get blog posts via HTMX
    """

    logger.debug("Getting blog posts for %s via HTMX", username)
    try:
        api = API(request, username, use_wordpress=True, create=False)

        profile_info_obj = api.get_profile_info()

        # Get the blog posts for this username
        user_blog_posts = (
            api.get_blog_posts()
            if profile_info_obj["profile"].show_blog_posts
            else None
        )

        return render(
            request,
            "newprofile/partials/blog_posts.html",
            {
                "blog_posts": user_blog_posts,
                "profile": profile_info_obj,
                "show_blog_posts": profile_info_obj["profile"].show_blog_posts,
            },
        )

    except django.db.utils.OperationalError as ex:
        logger.warning("Unable to connect to database for blog posts: %s", ex)
        # Return safe fallback context
        context = {
            "blog_posts": None,
            "profile": {"profile": None},
            "show_blog_posts": False,
        }
        return render(request, "newprofile/partials/blog_posts.html", context)


def cover_image(request, username):
    """
    Load the cover image via HTMX
    """
    logger.debug("Getting cover image for %s via HTMX", username)

    try:
        api = API(request, username, use_wordpress=True, create=False)

        return render(
            request,
            "newprofile/partials/cover_image.html",
            {"cover_image": api.get_cover_image()},
        )

    except django.db.utils.OperationalError as ex:
        logger.warning("Unable to connect to database for cover image: %s", ex)
        # Return safe fallback context
        context = {
            "cover_image": None,
        }
        return render(request, "newprofile/partials/cover_image.html", context)


def header_bar(request):
    """
    Get the header bar for the logged-in user via HTMX
    """
    logger.debug("Getting header bar for %s via HTMX", request.user)

    if request.user.is_authenticated:
        try:
            api_me = (
                API(
                    request,
                    request.user.username,
                    use_wordpress=True,
                    create=False,
                )
                if request.user.is_authenticated
                else None
            )

            my_profile_info = api_me.get_profile_info() if api_me else None
            notifications = (
                api_me.get_short_notifications() if api_me else None
            )

            context = {
                "username": request.user.username,
                "logged_in_profile": my_profile_info,
                "logged_in_user": (
                    request.user if request.user.is_authenticated else None
                ),
                "short_notifications": notifications,
                "notification_count": (
                    len(notifications) if notifications else 0
                ),
                "logout_url": reverse("logout"),
                "logged_in_profile_image": (
                    api_me.get_profile_photo() if api_me else None
                ),
            }

            return render(
                request,
                "newprofile/partials/header_bar.html",
                context=context,
            )

        except django.db.utils.OperationalError as ex:
            logger.warning(
                "Unable to connect to database for header bar: %s", ex
            )
            # Return safe fallback context
            context = {
                "username": request.user.username,
                "logged_in_profile": None,
                "logged_in_user": (
                    request.user if request.user.is_authenticated else None
                ),
                "short_notifications": None,
                "notification_count": 0,
            }
            return render(
                request,
                "newprofile/partials/mysql_data.html",
                context=context,
            )
    else:
        context = {
            "username": request.user.username,
            "logged_in_profile": None,
            "logged_in_user": (
                request.user if request.user.is_authenticated else None
            ),
            "short_notifications": None,
            "notification_count": 0,
        }
        return render(
            request,
            "newprofile/partials/mysql_data.html",
            context=context,
        )


def mysql_data(request, username):
    """
    Get WordPress data via HTMX
    """
    logger.debug("Getting MySQL data for %s via HTMX", username)

    try:
        api = API(request, username, use_wordpress=True, create=False)

        profile_info_obj = api.get_profile_info()

        if username == request.user.username:
            api_me = api
            my_profile_info = profile_info_obj
        else:
            # get logged in user profile
            api_me = (
                API(
                    request,
                    request.user.username,
                    use_wordpress=True,
                    create=False,
                )
                if request.user.is_authenticated
                else None
            )

            my_profile_info = api_me.get_profile_info() if api_me else None

        # this method is special and returns a boolean for MySql connection
        success, follower_count = api.follower_count()

        if success:
            context = {
                "username": username,
                "profile_image": api.get_profile_photo(),
                "groups": (
                    api.get_groups()
                    if profile_info_obj["profile"].show_commons_groups
                    else None
                ),
                "logged_in_profile": my_profile_info,
                "logged_in_user": (
                    request.user if request.user.is_authenticated else None
                ),
                "memberships": api.get_memberships(),
                "follower_count": (
                    follower_count if follower_count != "None" else 0
                ),
                "commons_sites": (
                    api.get_user_blogs()
                    if profile_info_obj["profile"].show_commons_sites
                    else None
                ),
                "activities": (
                    api.get_activity()
                    if profile_info_obj["profile"].show_recent_activity
                    else None
                ),
                "logout_url": reverse("logout"),
                "profile": profile_info_obj,
                "show_commons_groups": profile_info_obj[
                    "profile"
                ].show_commons_groups,
                "show_commons_sites": profile_info_obj[
                    "profile"
                ].show_commons_sites,
                "show_recent_activity": profile_info_obj[
                    "profile"
                ].show_recent_activity,
            }
        else:
            context = {
                "username": username,
                "cover_image": api.get_cover_image(),
                "groups": [],
                "logged_in_profile": my_profile_info,
                "logged_in_user": (
                    request.user if request.user.is_authenticated else None
                ),
                "memberships": [],
                "follower_count": None,
                "commons_sites": [],
                "activities": [],
                "short_notifications": None,
                "notification_count": 0,
                "logged_in_profile_image": (
                    api_me.get_profile_photo() if api_me else None
                ),
                "logout_url": None,
                "profile": profile_info_obj,
            }

        return render(
            request,
            "newprofile/partials/mysql_data.html",
            context=context,
        )

    except django.db.utils.OperationalError as ex:
        logger.warning("Unable to connect to database for MySQL data: %s", ex)
        # Return safe fallback context
        context = {
            "username": username,
            "cover_image": None,
            "profile_image": None,
            "groups": None,
            "logged_in_profile": None,
            "logged_in_user": None,
            "memberships": None,
            "follower_count": None,
            "commons_sites": None,
            "activities": None,
            "short_notifications": None,
            "notification_count": 0,
            "logged_in_profile_image": None,
            "logout_url": None,
            "profile": None,
        }
        return render(request, "newprofile/partials/mysql_data.html", context)


def profile_image(request, username):
    """
    Load the profile image via HTMX
    """
    logger.debug("Getting profile image for %s via HTMX", username)

    try:
        api = API(request, username, use_wordpress=True, create=False)

        return render(
            request,
            "newprofile/partials/profile_image.html",
            {
                "profile_image": api.get_profile_photo(),
                "username": username,
            },
        )

    except django.db.utils.OperationalError as ex:
        logger.warning(
            "Unable to connect to database for profile image: %s", ex
        )
        # Return safe fallback context
        context = {
            "profile_image": None,
            "username": username,
        }
        return render(
            request, "newprofile/partials/profile_image.html", context
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


def health(request):
    """
    Healthcheck URL
    """
    health_result = {}
    fail = False

    try:
        cache.set("health", "healthy", REDIS_TEST_TIMEOUT_VALUE)
        _ = cache.get("health")
    except redis.exceptions.ConnectionError as ce:
        health_result["REDIS"] = f"unhealthy: {ce}"
        fail = True
    else:
        health_result["REDIS"] = "healthy"

    try:
        # Test WordPress database connection
        db_conn = connections["wordpress_dev"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError as oe:
        health_result["WordPress DB"] = f"unhealthy: {oe}"
        fail = True
    else:
        health_result["WordPress DB"] = "healthy"

    try:
        # Test PostGres database connection
        db_conn = connections["default"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError as oe:
        health_result["Postgres DB"] = f"unhealthy: {oe}"
        fail = True
    else:
        health_result["Postgres DB"] = "healthy"

    health_result["Debug Mode"] = settings.DEBUG

    health_result["VERSION"] = VERSION

    return JsonResponse(health_result, status=200 if not fail else 500)


@basic_auth_required
def stats_board(request):
    """
    The stats dashboard
    """

    logger.debug("Getting stats dashboard for %s", request.user)

    stats = UserStats.objects.all().first()

    users = WpUser.get_user_data(limit=10)

    context = {
        "user_count": stats.user_count,
        "user_count_active": stats.user_count_active,
        "user_count_active_two": stats.user_count_active_two,
        "user_count_active_three": stats.user_count_active_three,
        "years": stats.years,
        "data": stats.data,
        "latlong": json.loads(stats.latlong),
        "topinsts": stats.topinsts,
        "topinstscount": stats.topinstscount,
        "emails": stats.emails,
        "emailcount": stats.emailcount,
        "users": users,
    }

    return render(request, "newprofile/dashboard.html", context)


@basic_auth_required
def stats_download(request):
    """
    The stats CSV download
    """

    logger.debug("Downloading stats for %s", request.user)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'

    WpUser.get_user_data(limit=-1, output_stream=response)

    return response


@basic_auth_required
def stats_table(request):
    """
    The stats table
    """

    logger.debug("Getting stats table for %s", request.user)

    users = WpUser.get_user_data(limit=-1)

    return render(
        request, "newprofile/partials/stats_table.html", {"users": users}
    )
