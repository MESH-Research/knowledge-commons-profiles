"""
URL configuration for rest_api project.

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

from django.urls import path

from knowledge_commons_profiles.rest_api.views import GroupView
from knowledge_commons_profiles.rest_api.views import ProfileView

urlpatterns = [
    path(
        r"api/v1/users/<str:user_name>/",
        ProfileView.as_view(),
        name="profile_rest_view",
    ),
    path(
        r"api/v1/groups/<int:pk>/",
        GroupView.as_view(),
        name="group_rest_view",
    ),
    path(
        r"api/v1/groups/<str:slug>/",
        GroupView.as_view(),
        name="group_slug_rest_view",
    ),
]
