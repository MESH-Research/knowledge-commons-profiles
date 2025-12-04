# htmx view functions
import logging

import django.db
from django.shortcuts import render
from django.urls import reverse

from knowledge_commons_profiles.newprofile.api import API

logger = logging.getLogger(__name__)


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

        orgs = api.profile.get_external_memberships()

        for org, is_member in orgs.items():
            if is_member:
                context[org] = (
                    org in context["profile_info"]["is_member_of"]
                    and context["profile_info"]["is_member_of"][org]
                )

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
            "MLA": False,
            "UP": False,
            "ARLISNA": False,
            "MSU": False,
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
        nocache = request.GET.get("nocache", "").lower() in (
            "true",
            "1",
            "yes",
        )

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
            {"cover_image": api.get_cover_image(), "username": username},
        )

    except django.db.utils.OperationalError as ex:
        logger.warning("Unable to connect to database for cover image: %s", ex)
        # Return safe fallback context
        context = {
            "cover_image": None,
            "username": username,
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
                "logout_url": reverse("logout"),
            }
            return render(
                request,
                "newprofile/partials/header_bar.html",
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
            "newprofile/partials/header_bar.html",
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
                "logout_url": reverse("logout"),
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
            "logout_url": reverse("logout"),
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
        img = api.get_profile_photo()

        msg = f"Profile image for {username}: {img}"
        logger.debug(msg)

        return render(
            request,
            "newprofile/partials/profile_image.html",
            {
                "profile_image": img,
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
