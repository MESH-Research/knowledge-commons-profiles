# htmx view functions
import logging

import django.db
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse

from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.works import WorksApiError

# Short TTL for HTMX fragment caches. Long enough that the second hit of a
# profile page (same user clicks through and comes back) is a Redis GET;
# short enough that user-visible profile edits show up within a minute
# without explicit invalidation.
HTMX_FRAGMENT_CACHE_TTL = 60

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
            "show_memberships": api.profile.show_memberships,
        }

        orgs = api.profile.get_external_memberships()

        org_name: str

        for org_name, is_member in orgs.items():
            if is_member:
                key = (
                    "STEMEDPLUS" if org_name.upper() == "STEMED+" else org_name
                )
                context[key] = True

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
            "show_memberships": False,
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

    cache_key = f"htmx_works_deposits:{username}:{style or 'default'}"
    cached_html = cache.get(cache_key)
    if cached_html is not None:
        return HttpResponse(cached_html)

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

        # Skip both the works data and the chart when the user has hidden
        # the panel — the chart pulls and reshapes the works data, so it's
        # pure waste when the panel won't render.
        if api.profile.show_works:
            user_works_deposits = api.works_html
            chart = api.works_chart_json
        else:
            user_works_deposits = []
            chart = "{}"

        html = render_to_string(
            "newprofile/partials/works_deposits.html",
            {
                "works_headings_ordered": user_works_deposits,
                "works_html": user_works_deposits,
                "profile": api.profile,
                "show_works": api.profile.show_works,
                "chart": chart,
            },
            request=request,
        )
        cache.set(cache_key, html, timeout=HTMX_FRAGMENT_CACHE_TTL)
        return HttpResponse(html)

    except (django.db.utils.OperationalError, WorksApiError) as ex:
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

        # Get the mastodon posts for this username. api.mastodon_posts
        # is None when the stored handle is missing or fails parsing.
        user_mastodon_posts = (
            (
                api.mastodon_posts.latest_posts(nocache=nocache)
                if api.profile_info["mastodon"] and api.mastodon_posts
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

            # get the username
            api_me = (
                API(
                    request,
                    request.user.username,
                    use_wordpress=False,
                    create=False,
                )
                if request.user.is_authenticated
                else None
            )

            profile = api_me.profile if api_me else None

            # Return safe fallback context
            context = {
                "username": request.user.username,
                "logged_in_profile": profile,
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
        profile_model = profile_info_obj["profile"]

        # this method is special and returns a boolean for MySql connection
        success, follower_count = api.follower_count()

        if success:
            groups = (
                api.get_groups() if profile_model.show_commons_groups else []
            )
            commons_sites = (
                api.get_user_blogs()
                if profile_model.show_commons_sites
                else []
            )
            activities = (
                api.get_activity()
                if profile_model.show_recent_activity
                else []
            )
            follower_count_value = (
                follower_count if follower_count != "None" else 0
            )
        else:
            groups = []
            commons_sites = []
            activities = []
            follower_count_value = None

        context = {
            "follower_count": follower_count_value,
            "groups": groups,
            "activities": activities,
            "commons_sites": commons_sites,
            "profile": profile_info_obj,
            "wordpress_domain": settings.WORDPRESS_DOMAIN,
        }

        return render(
            request,
            "newprofile/partials/mysql_data.html",
            context=context,
        )

    except django.db.utils.OperationalError as ex:
        logger.warning("Unable to connect to database for MySQL data: %s", ex)
        # Safe fallback. profile=None makes the template's
        # `profile.profile.show_*` lookups silently falsy, so every panel
        # renders in its hide-state without raising.
        context = {
            "follower_count": None,
            "groups": [],
            "activities": [],
            "commons_sites": [],
            "profile": None,
            "wordpress_domain": settings.WORDPRESS_DOMAIN,
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
