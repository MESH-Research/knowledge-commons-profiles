"""
The main views for the profile app
"""

from django.shortcuts import render

from newprofile.api import API
from newprofile.models import WpBlog


def home(request, user=""):
    """
    The main page of the site.

    This view renders the main page of the site.
    """
    api = API(request, user)

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
