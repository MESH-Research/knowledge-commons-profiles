"""
The main views for the profile app
"""

import datetime
import json
import logging

import django
import redis
from basicauth.decorators import basic_auth_required
from django.conf import settings
from django.contrib.auth import logout
from django.core.cache import cache
from django.db import connections
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.custom_login import login_required
from knowledge_commons_profiles.newprofile.custom_login import wp_create_nonce
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import process_orders
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)
from knowledge_commons_profiles.newprofile.works import CACHE_TIMEOUT
from knowledge_commons_profiles.newprofile.works import HiddenWorks

logger = logging.getLogger(__name__)

REDIS_TEST_TIMEOUT_VALUE = 25


def profile_info(request, username):
    """
    Get profile info via HTMX
    """
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

    return render(request, "newprofile/partials/profile_info.html", context)


def works_deposits(request, username, style=None):
    """
    Get profile info via HTMX
    """
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


def mastodon_feed(request, username):
    """
    Get a mastodon feed via HTMX
    """
    api = API(request, username, use_wordpress=False, create=False)

    profile_info_obj = api.get_profile_info()

    # Get the mastodon posts for this username
    mastodon_posts = (
        (
            api.mastodon_posts.latest_posts
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
            "mastodon_posts": mastodon_posts,
            "profile": profile_info_obj,
            "show_mastodon_feed": profile_info_obj[
                "profile"
            ].show_mastodon_feed,
        },
    )


def logout_view(request):
    """
    A view to log out the current user.

    This view logs out the current user and redirects them to the login page.

    :param request: The request object.
    :type request: django.http.HttpRequest
    """
    logout(request)


def profile(request, user=""):
    """
    The main page of the site.

    This view renders the main page of the site.
    """

    if not profile_exists_or_has_been_created(user):
        raise Http404

    api: API = API(request, user, use_wordpress=False, create=False)

    profile_obj: Profile = api.profile

    # if the logged-in user is the same as the requested profile they are
    # viewing, we should show the edit navigation
    logged_in_user_is_profile: bool = request.user.username == user

    left_order: list = (
        json.loads(profile_obj.left_order) if profile_obj.left_order else []
    )
    right_order: list = (
        json.loads(profile_obj.right_order) if profile_obj.right_order else []
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


@login_required
def my_profile(request):
    """
    A view for logged-in users to view their own profile page.

    If the user is logged in, this view will redirect them to the main page
    with their username as the user parameter.

    :param request: The request object.
    :type request: django.http.HttpRequest
    """
    # we call with create because this user is logged in and needs a profile
    return profile(request, user=request.user.username)


class ProfileView(APIView):
    """
    A REST view for retrieving and updating user profile information
    """

    def get(self, request, *args, **kw):
        """
        Return a JSON response containing the user's profile information,
        academic interests, education, a short string about the user,
        their latest blog posts, their latest Mastodon posts (if they have
        a Mastodon account), and a string representing their works.

        The response is returned with a status of 200 OK.

        :param request: The request object.
        :type request: django.http.HttpRequest
        :param args: Additional positional arguments.
        :type args: list
        :param kw: Additional keyword arguments.
        :type kw: dict
        :return: A JSON response containing the user's profile information.
        :rtype: django.http.JsonResponse
        """

        user = kw.get("user_name", "")

        api = API(request, user, use_wordpress=True)

        profile_info_obj = api.get_profile_info()

        context = {
            "profile_info": profile_info_obj,
            "education": api.get_education(),
            "about_user": api.get_about_user(),
            "mastodon_posts": (
                api.mastodon_posts.latest_posts
                if profile_info_obj["mastodon"]
                else []
            ),
            # "groups": api.get_groups(),
            "memberships": api.get_memberships(),
        }

        return Response(context, status=status.HTTP_200_OK)


@login_required
@require_POST
def works_deposits_edit(request):
    """
    A view for logged-in users to edit their works.
    """

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

    user = Profile.objects.prefetch_related("academic_interests").get(
        username=request.user
    )

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
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
    except django.db.utils.OperationalError:
        logger.warning("Unable to connect to MySQL database for blogs")
        return render(
            request,
            "newprofile/partials/blog_posts.html",
            {"blog_posts": ""},
        )


def cover_image(request, username):
    """
    Load the cover image via HTMX
    """
    api = API(request, username, use_wordpress=True, create=False)

    return render(
        request,
        "newprofile/partials/cover_image.html",
        {"cover_image": api.get_cover_image()},
    )


def header_bar(request):
    if request.user.is_authenticated:
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
        notifications = api_me.get_short_notifications() if api_me else None

        context = {
            "username": request.user.username,
            "logged_in_profile": my_profile_info,
            "logged_in_user": (
                request.user if request.user.is_authenticated else None
            ),
            "short_notifications": notifications,
            "notification_count": (len(notifications) if notifications else 0),
            "logout_url": f"https://hcommons.org/wp-login.php?"
            f"action=logout&"
            f"_wpnonce={wp_create_nonce(request=request)}&"
            f"redirect_to={request.build_absolute_uri()}",
            "logged_in_profile_image": (
                api_me.get_profile_photo() if api_me else None
            ),
        }

        return render(
            request,
            "newprofile/partials/header_bar.html",
            context=context,
        )

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
                "logout_url": f"https://hcommons.org/wp-login.php?"
                f"action=logout&"
                f"_wpnonce={wp_create_nonce(request=request)}&"
                f"redirect_to={request.build_absolute_uri()}",
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
        logger.warning("Unable to connect to MySQL database: %s", ex)
        context = {
            "username": None,
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
        return render(request, "newprofile/partials/mysql_data.html", {})


def profile_image(request, username):
    """
    Load the profile image
    """
    api = API(request, username, use_wordpress=True, create=False)

    return render(
        request,
        "newprofile/partials/profile_image.html",
        {
            "profile_image": api.get_profile_photo(),
            "username": username,
        },
    )


@login_required
@require_POST
def save_works_visibility(request):
    """
    Save the visibility of the user's Works headings via AJAX
    """
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
def stats_board(request):  # noqa: C901
    cache.delete("user_data", version=VERSION)
    cache.delete("user_count_active", version=VERSION)
    cache.delete("user_count_active_two", version=VERSION)
    cache.delete("user_count_active_three", version=VERSION)

    users = cache.get("user_data", version=VERSION)

    if not users:
        # users = models.WpUser.get_user_data()
        # make a dummy list of dict[str, strs] with these fields:

        users = [
            {
                "id": "12",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2016-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "12",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2014-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "12",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2015-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "12",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2014-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "12",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2014-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "1",
                "display_name": "John Doe",
                "user_login": "jdoe",
                "user_email": "jdoe@uw.edu",
                "institution": "UW",
                "date_registered": "2022-01-01 01:00:00+00:00",
                "latest_activity": "2022-01-01 01:00:00+00:00",
            },
            {
                "id": "2",
                "display_name": "Jane Doe",
                "user_login": "jane",
                "user_email": "jane@uw.edu",
                "institution": "UW",
                "date_registered": "2023-01-01 01:00:00+00:00",
                "latest_activity": "2023-01-01 01:00:00+00:00",
            },
            {
                "id": "2",
                "display_name": "Jane Doe",
                "user_login": "jane",
                "user_email": "jane@uw.edu",
                "institution": "UW",
                "date_registered": "2025-02-01 01:00:00+00:00",
                "latest_activity": "2024-01-01 01:00:00+00:00",
            },
            {
                "id": "2",
                "display_name": "Jane Doe",
                "user_login": "jane",
                "user_email": "jane@uw.edu",
                "institution": "UW",
                "date_registered": "2025-01-01 01:00:00+00:00",
                "latest_activity": "2025-01-01 01:00:00+00:00",
            },
        ]

        cache.set("user_data", users, version=VERSION, timeout=CACHE_TIMEOUT)

    user_count_active = cache.get(
        "user_count_active", version=VERSION, default=0
    )

    user_count_active_two = cache.get(
        "user_count_active_two", version=VERSION, default=0
    )

    user_count_active_three = cache.get(
        "user_count_active_three", version=VERSION, default=0
    )

    if (
        not user_count_active
        or not user_count_active_two
        or not user_count_active_three
    ):
        user_count_active = 0
        user_count_active_two = 0
        user_count_active_three = 0

        for user in users:
            try:
                # parse "latest_activity" key as a python date
                user_date_of_last_activity = datetime.datetime.strptime(
                    user["latest_activity"], "%Y-%m-%d %H:%M:%S+00:00"
                ).replace(tzinfo=datetime.UTC)
            except (ValueError, TypeError):
                continue

            if user_date_of_last_activity > datetime.datetime.now(
                tz=datetime.UTC
            ) - datetime.timedelta(weeks=166):
                user_count_active += 1

            if user_date_of_last_activity > datetime.datetime.now(
                tz=datetime.UTC
            ) - datetime.timedelta(weeks=104):
                user_count_active_two += 1

            if user_date_of_last_activity > datetime.datetime.now(
                tz=datetime.UTC
            ) - datetime.timedelta(weeks=52):
                user_count_active_three += 1

        cache.set(
            "user_count_active",
            user_count_active,
            version=VERSION,
            timeout=CACHE_TIMEOUT,
        )

        cache.set(
            "user_count_active_two",
            user_count_active_two,
            version=VERSION,
            timeout=CACHE_TIMEOUT,
        )

        cache.set(
            "user_count_active_three",
            user_count_active_three,
            version=VERSION,
            timeout=CACHE_TIMEOUT,
        )

    # build a dictionary of signups by year since 2014 and add keys from 2014
    # to the current year with default value of zero
    signups_by_year = {}

    for year in range(2014, datetime.datetime.now(tz=datetime.UTC).year + 1):
        signups_by_year[str(year)] = 0

    # now get the date_registered count for each year
    for user in users:
        try:
            # parse "date_registered" key as a python date
            user_date_registered = datetime.datetime.strptime(
                user["date_registered"], "%Y-%m-%d %H:%M:%S+00:00"
            ).replace(tzinfo=datetime.UTC)

            signups_by_year[str(user_date_registered.year)] += 1
        except (ValueError, TypeError):
            continue

    context = {
        "user_count": len(users),
        "user_count_active": user_count_active,
        "user_count_active_two": user_count_active_two,
        "user_count_active_three": user_count_active_three,
        "years": str(list(signups_by_year.keys())),
        "data": str(list(signups_by_year.values())),
    }

    return render(request, "newprofile/dashboard.html", context)
