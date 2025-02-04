"""
The main views for the profile app
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from newprofile.api import API


@login_required
def home(request, user=""):
    """
    The main page of the site.

    This view renders the main page of the site.
    """
    api = API(request, user, use_wordpress=False)

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

    return render(request=request, context=context, template_name="home.html")


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

    def post(self, request, *args, **kw):
        """
        Update the user's profile information.

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

        print(request.data)

        # api.update_profile(request.data)

        return self.get(request, *args, **kw)
