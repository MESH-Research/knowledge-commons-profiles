"""
URL configuration for cilogon project.

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
from django.urls import path

from knowledge_commons_profiles.cilogon import views

urlpatterns = [
    path("login/", views.cilogon_login, name="login"),
    path("logout/", views.app_logout, name="logout"),
    path(settings.OIDC_CALLBACK, views.callback, name="oidc_callback"),
    path("associate/", views.association, name="associate"),
    path("register/", views.register, name="user_registration"),
    path("confirm/", views.confirm, name="confirm"),
    path(
        "user-updated/", views.user_updated, name="user_update_webhook"
    ),  # dummy user updated rule to simulate remote API for testing
    path(
        "members/<str:user_name>/settings/",
        views.manage_login,
        name="manage_login",
    ),
    path(
        "members/<str:user_name>/roles/",
        views.manage_roles,
        name="manage_roles",
    ),
    path(
        "activate/<int:verification_id>/<str:secret_key>/",
        views.activate,
        name="activate",
    ),
    path(
        "new-email/<int:verification_id>/<str:secret_key>/",
        views.new_email_verified,
        name="new_email",
    ),
]
