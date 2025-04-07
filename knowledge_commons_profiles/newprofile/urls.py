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

from knowledge_commons_profiles.newprofile import views
from knowledge_commons_profiles.newprofile.views import ProfileView
from knowledge_commons_profiles.newprofile.views import logout_view

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
    path("logout/", logout_view, name="logout_to_remove"),
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
]
