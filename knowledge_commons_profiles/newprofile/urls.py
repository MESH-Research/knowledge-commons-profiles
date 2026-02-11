"""
URL configuration for newprofile project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import include
from django.urls import path

from knowledge_commons_profiles.newprofile.views.home import home
from knowledge_commons_profiles.newprofile.views.members import (
    people_by_username,
)
from knowledge_commons_profiles.newprofile.views.profile.avatars import (
    upload_avatar,
)
from knowledge_commons_profiles.newprofile.views.profile.avatars import (
    upload_cover,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import blog_posts
from knowledge_commons_profiles.newprofile.views.profile.htmx import cover_image
from knowledge_commons_profiles.newprofile.views.profile.htmx import header_bar
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    mastodon_feed,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import mysql_data
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    profile_image,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    profile_info,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    works_deposits,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    edit_profile,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    my_profile,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import profile
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    save_profile_order,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    toggle_superadmin_rights_with_permission,
)
from knowledge_commons_profiles.newprofile.views.profile.works import (
    save_works_order,
)
from knowledge_commons_profiles.newprofile.views.profile.works import (
    save_works_visibility,
)
from knowledge_commons_profiles.newprofile.views.profile.works import (
    works_deposits_edit,
)
from knowledge_commons_profiles.newprofile.views.search import search
from knowledge_commons_profiles.newprofile.views.stats import stats_board
from knowledge_commons_profiles.newprofile.views.stats import stats_download
from knowledge_commons_profiles.newprofile.views.stats import stats_table

urlpatterns = [
    path("my-profile/", my_profile, name="my_profile"),
    path("edit-profile/", edit_profile, name="edit_profile"),
    path(
        "edit-profile/<str:username>/makesuperuser/",
        toggle_superadmin_rights_with_permission,
        name="toggle_superadmin",
    ),
    path("edit-profile/upload-avatar/", upload_avatar, name="upload_avatar"),
    path("edit-profile/upload-cover/", upload_cover, name="upload_cover"),
    path("members/<str:user>/", profile, name="profile"),
    path("members/<str:user>/profile/", profile, name="alternative_profile_1"),
    path("api-auth/", include("rest_framework.urls")),
    path("tinymce/", include("tinymce.urls")),
    path(
        "htmx/mastodon-feed/<str:username>/",
        mastodon_feed,
        name="mastodon_feed",
    ),
    path(
        "htmx/blog-posts/<str:username>/",
        blog_posts,
        name="blog_posts",
    ),
    path(
        "htmx/works-deposits/<str:username>/",
        works_deposits,
        name="works_deposits",
    ),
    path(
        "htmx/works-deposits/<str:username>/<str:style>/",
        works_deposits,
        name="works_deposits_style",
    ),
    path(
        "htmx/profile-info/<str:username>/",
        profile_info,
        name="profile_info",
    ),
    path(
        "htmx/mysql-data/<str:username>/",
        mysql_data,
        name="mysql_data",
    ),
    path(
        "htmx/cover-image/<str:username>/",
        cover_image,
        name="cover_image",
    ),
    path(
        "htmx/profile-image/<str:username>/",
        profile_image,
        name="profile_image",
    ),
    path(
        "htmx/header-bar/",
        header_bar,
        name="header_bar",
    ),
    path(
        "save-profile-order/<str:side>/",
        save_profile_order,
        name="save_profile_order",
    ),
    path(
        "save-works-order/",
        save_works_order,
        name="save_works_order",
    ),
    path(
        "save-works-visibility/",
        save_works_visibility,
        name="save_works_visibility",
    ),
    path(
        "works-deposits-edit/",
        works_deposits_edit,
        name="works_deposits_edit",
    ),
    path("stats/", stats_board, name="stats"),
    path("stats/download/", stats_download, name="get_stats_csv"),
    path("stats/table/", stats_table, name="stats_table"),
    path("members/", people_by_username, name="members"),
    path("search/", search, name="search"),
    path("", home, name="home"),
]
