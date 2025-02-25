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

import django_saml2_auth.views
from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf.urls.static import static
from django.urls import path, include, re_path

from newprofile import views, settings
from newprofile.views import ProfileView, logout_view

urlpatterns = (
    [
        # These are the SAML2 related URLs. (required)
        re_path(r"^sso/", include("django_saml2_auth.urls")),
        # The following line will replace the default user login with SAML2 (optional)
        # If you want to specific the after-login-redirect-URL, use parameter "?next=/the/path/you/want"
        # with this view.
        re_path(r"^accounts/login/$", django_saml2_auth.views.signin),
        # The following line will replace the admin login with SAML2 (optional)
        # If you want to specific the after-login-redirect-URL, use parameter "?next=/the/path/you/want"
        # with this view.
        re_path(r"^admin/login/$", django_saml2_auth.views.signin),
        path("select2/", include("django_select2.urls")),
        path(
            r"api/v1.0/user/<str:user_name>/",
            ProfileView.as_view(),
            name="profile_rest_view",
        ),
        path("my_profile/", views.my_profile, name="my_profile"),
        path("edit_profile/", views.edit_profile, name="edit_profile"),
        path("user/<str:user>/", views.profile, name="user_profile"),
        re_path("member/<str:user>/", views.profile, name="profile"),
        path("api-auth/", include("rest_framework.urls")),
        path("logout/", logout_view, name="logout_to_remove"),
        path("tinymce/", include("tinymce.urls")),
        path(
            "htmx/mastodon_feed/<str:username>/",
            views.mastodon_feed,
            name="mastodon_feed",
        ),
        path(
            "htmx/blog_posts/<str:username>/",
            views.blog_posts,
            name="blog_posts",
        ),
        path(
            "htmx/works_deposits/<str:username>/",
            views.works_deposits,
            name="works_deposits",
        ),
        path(
            "htmx/profile_info/<str:username>/",
            views.profile_info,
            name="profile_info",
        ),
        path(
            "htmx/mysql_data/<str:username>/",
            views.mysql_data,
            name="mysql_data",
        ),
    ]
    + debug_toolbar_urls()
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)
