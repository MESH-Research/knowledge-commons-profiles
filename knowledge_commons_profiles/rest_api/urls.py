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
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from knowledge_commons_profiles.rest_api.views import GroupDetailView
from knowledge_commons_profiles.rest_api.views import LogoutView
from knowledge_commons_profiles.rest_api.views import ProfileDetailView
from knowledge_commons_profiles.rest_api.views import ProfileListView
from knowledge_commons_profiles.rest_api.views import SubListView
from knowledge_commons_profiles.rest_api.views import SubSingleView
from knowledge_commons_profiles.rest_api.views import TokenPutView

SchemaView = get_schema_view(
    openapi.Info(
        title="Knowledge Commons IDMS API",
        default_version="v1",
        description="An API for the Knowledge Commons IDMS",
        contact=openapi.Contact(email="hello@hcommons.org"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)
urlpatterns = [
    path(
        "api/v1/swagger/",
        SchemaView.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/v1/redoc/",
        SchemaView.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
    path(
        "api/v1/swagger.json",
        SchemaView.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        r"api/v1/actions/logout/",
        LogoutView.as_view(),
        name="actions_post_view",
    ),
    path(
        r"api/v1/subs/",
        SubListView.as_view(),
        name="subs_list_view",
    ),
    path(
        r"api/v1/subs/<str:username>/",
        SubSingleView.as_view(),
        name="single_subs_list_view",
    ),
    path(
        r"api/v1/tokens/",
        TokenPutView.as_view(),
        name="tokens_put_view",
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
