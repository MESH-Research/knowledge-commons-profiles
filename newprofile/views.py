"""
The main views for the profile app
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from newprofile.api import API
from django.contrib.auth import logout


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
    api = API(request, user, use_wordpress=False, create=create)

    # TODO: if "create" then redirect to the profile edit page

    profile_info = api.get_profile_info()

    context = {
        "profile_info": profile_info,
        "academic_interests": api.get_academic_interests(),
        "education": api.get_education(),
        "about_user": api.get_about_user(),
        "blog_posts": api.get_blog_posts(),
        "mastodon_posts": (
            api.mastodon_posts.latest_posts if profile_info["mastodon"] else []
        ),
        "works_html": api.works_html,
    }

    return render(
        request=request, context=context, template_name="profile.html"
    )


@login_required
def my_profile(request):
    """
    A view for logged-in users to view their own profile page.

    If the user is logged in, this view will redirect them to the main page with
    their username as the user parameter.

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

        api = API(request, user, use_wordpress=False)

        profile_info = api.get_profile_info()

        context = {
            "profile_info": profile_info,
            "academic_interests": api.get_academic_interests(),
            "education": api.get_education(),
            "about_user": api.get_about_user(),
            # "blog_posts": api.get_blog_posts(),
            "mastodon_posts": (
                api.mastodon_posts.latest_posts
                if profile_info["mastodon"]
                else []
            ),
            "works_html": api.works_html,
        }

        response = Response(context, status=status.HTTP_200_OK)
        return response
