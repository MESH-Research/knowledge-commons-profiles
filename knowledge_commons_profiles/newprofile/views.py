"""
The main views for the profile app
"""

import logging

import django
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


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
    }

    return render(request, "newprofile/partials/profile_info.html", context)


async def works_deposits(request, username):
    """
    Get profile info via HTMX
    """
    api = API(request, username, use_wordpress=False, create=False)

    # Get the works deposits for this username
    user_works_deposits = await api.works_html

    return render(
        request,
        "newprofile/partials/works_deposits.html",
        {"works_html": user_works_deposits},
    )


def mastodon_feed(request, username):
    """
    Get a mastodon feed via HTMX
    """
    api = API(request, username, use_wordpress=False, create=False)

    # Get the mastodon posts for this username
    mastodon_posts = (
        api.mastodon_posts.latest_posts if api.profile_info["mastodon"] else []
    )

    return render(
        request,
        "newprofile/partials/mastodon_feed.html",
        {"mastodon_posts": mastodon_posts},
    )


def logout_view(request):
    """
    A view to log out the current user.

    This view logs out the current user and redirects them to the login page.

    :param request: The request object.
    :type request: django.http.HttpRequest
    """
    logout(request)


def profile(request, user="", create=False):
    """
    The main page of the site.

    This view renders the main page of the site.
    """
    # TODO: if "create" then redirect to the profile edit page

    # the logged-in user is the same as the requested profile they are
    # viewing. This means we should show the edit navigation

    logged_in_user_is_profile = request.user.username == user

    return render(
        request=request,
        context={
            "username": user,
            "logged_in_user_is_profile": logged_in_user_is_profile,
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
    return profile(request, user=request.user.username, create=True)


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
    # user = Profile.objects.prefetch_related("academic_interests").get(
    #    username=request.user.username
    # )

    user = Profile.objects.prefetch_related("academic_interests").get(
        username="kfitz",
    )

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
    else:
        form = ProfileForm(instance=user)

    return render(
        request,
        "newprofile/edit_profile.template",
        {"form": form, "profile": user},
    )


def blog_posts(request, username):
    """
    Get blog posts via HTMX
    """
    try:
        api = API(request, username, use_wordpress=True, create=False)

        # Get the blog posts for this username
        user_blog_posts = api.get_blog_posts()

        return render(
            request,
            "newprofile/partials/blog_posts.html",
            {"blog_posts": user_blog_posts},
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

            notifications = (
                api_me.get_short_notifications() if api_me else None
            )

            context = {
                "username": username,
                "profile_image": api.get_profile_photo(),
                "groups": api.get_groups(),
                "logged_in_profile": my_profile_info,
                "logged_in_user": (
                    request.user if request.user.is_authenticated else None
                ),
                "memberships": api.get_memberships(),
                "follower_count": follower_count,
                "commons_sites": api.get_user_blogs(),
                "activities": api.get_activity(),
                "short_notifications": notifications,
                "notification_count": (
                    len(notifications) if notifications else 0
                ),
                "logged_in_profile_image": (
                    api_me.get_profile_photo() if api_me else None
                ),
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


def health(request):
    """
    Healthcheck URL
    """
    return HttpResponse("OK")
