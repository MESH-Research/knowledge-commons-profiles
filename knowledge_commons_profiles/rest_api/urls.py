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

from knowledge_commons_profiles.rest_api.views import GroupDetailView
from knowledge_commons_profiles.rest_api.views import ProfileDetailView
from knowledge_commons_profiles.rest_api.views import ProfileListView
from knowledge_commons_profiles.rest_api.views import SubListView

urlpatterns = [
    path(
        r"api/v1/subs/",
        SubListView.as_view(),
        name="profiles_list_view",
    ),
    path(
        r"api/v1/users/",
        ProfileListView.as_view(),
        name="profiles_list_view",
    ),
    path(
        r"api/v1/users/<str:user_name>/",
        ProfileDetailView.as_view(),
        name="profiles_detail_view",
    ),
    path(
        r"api/v1/groups/<int:pk>/",
        GroupDetailView.as_view(),
        name="groups_detail_view",
    ),
    path(
        r"api/v1/groups/<str:slug>/",
        GroupDetailView.as_view(),
        name="groups_slug_detail_view",
    ),
]
