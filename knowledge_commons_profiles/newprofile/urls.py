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

from django.conf import settings
from django.urls import include
from django.urls import path

from knowledge_commons_profiles.newprofile import views
from knowledge_commons_profiles.newprofile.views import ProfileView

urlpatterns = [
    path(
        r"api/v1.0/member/<str:user_name>/",
        ProfileView.as_view(),
        name="profile_rest_view",
    ),
    path("my-profile/", views.my_profile, name="my_profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("member/<str:user>/", views.profile, name="profile"),
    path("api-auth/", include("rest_framework.urls")),
    path("tinymce/", include("tinymce.urls")),
    path(
        "htmx/mastodon-feed/<str:username>/",
        views.mastodon_feed,
        name="mastodon_feed",
    ),
    path(
        "htmx/blog-posts/<str:username>/",
        views.blog_posts,
        name="blog_posts",
    ),
    path(
        "htmx/works-deposits/<str:username>/",
        views.works_deposits,
        name="works_deposits",
    ),
    path(
        "htmx/works-deposits/<str:username>/<str:style>/",
        views.works_deposits,
        name="works_deposits_style",
    ),
    path(
        "htmx/profile-info/<str:username>/",
        views.profile_info,
        name="profile_info",
    ),
    path(
        "htmx/mysql-data/<str:username>/",
        views.mysql_data,
        name="mysql_data",
    ),
    path(
        "htmx/cover-image/<str:username>/",
        views.cover_image,
        name="cover_image",
    ),
    path(
        "htmx/profile-image/<str:username>/",
        views.profile_image,
        name="profile_image",
    ),
    path(
        "htmx/header-bar/",
        views.header_bar,
        name="header_bar",
    ),
    path(
        "save-profile-order/<str:side>/",
        views.save_profile_order,
        name="save_profile_order",
    ),
    path(
        "save-works-order/",
        views.save_works_order,
        name="save_works_order",
    ),
    path(
        "save-works-visibility/",
        views.save_works_visibility,
        name="save_works_visibility",
    ),
    path(
        "works-deposits-edit/",
        views.works_deposits_edit,
        name="works_deposits_edit",
    ),
    path("stats/", views.stats_board, name="stats"),
    path("stats/download/", views.stats_download, name="get_stats_csv"),
    path("stats/table/", views.stats_table, name="stats_table"),
    # oAuth views
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path(settings.OIDC_CALLBACK, views.callback, name="oidc_callback"),
]
