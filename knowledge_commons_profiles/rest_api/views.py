"""
The REST API for the profile app
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.views import RedirectBehaviour
from knowledge_commons_profiles.cilogon.views import app_logout
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.rest_api.authentication import (
    HasStaticBearerToken,
)
from knowledge_commons_profiles.rest_api.authentication import (
    StaticBearerAuthentication,
)
from knowledge_commons_profiles.rest_api.errors import RESTError
from knowledge_commons_profiles.rest_api.pagination import (
    ProfileCursorPagination,
)
from knowledge_commons_profiles.rest_api.pagination import (
    SubProfileCursorPagination,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    GroupDetailSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    LogoutSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    ProfileDetailSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    ProfileSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    SingleSubProfileSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    SubProfileSerializer,
)
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    TokenSerializer,
)
from knowledge_commons_profiles.rest_api.sync import ExternalSync
from knowledge_commons_profiles.rest_api.utils import build_metadata
from knowledge_commons_profiles.rest_api.utils import logout_all_endpoints_sync

logger = logging.getLogger(__name__)


class SubListView(generics.ListAPIView):
    """
    List all profiles
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    queryset = SubAssociation.objects.all()

    serializer_class = SubProfileSerializer
    pagination_class = SubProfileCursorPagination

    def get_queryset(self):
        sub = self.request.GET.get("sub")

        if not sub:
            raise Http404

        return SubAssociation.objects.filter(sub=sub)


class SubSingleView(generics.ListAPIView):
    """
    List subs for an account
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    queryset = SubAssociation.objects.select_related("profile")

    lookup_field = "profile__username"
    lookup_url_kwarg = "username"

    serializer_class = SingleSubProfileSerializer
    pagination_class = SubProfileCursorPagination

    def get_queryset(self):
        # select_related avoids an extra query when touching profile
        return SubAssociation.objects.select_related("profile")

    def get_object(self):
        username = self.kwargs[self.lookup_url_kwarg]
        return SubAssociation.objects.filter(profile__username=username)


class ProfileListView(generics.ListAPIView):
    """
    List all profiles
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    queryset = (
        Profile.objects.all()
        .prefetch_related("academic_interests")
        .order_by("username")
    )

    serializer_class = ProfileSerializer
    pagination_class = ProfileCursorPagination


class ProfileDetailView(generics.RetrieveAPIView):
    """
    Retrieve a profile
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]
    queryset = Profile.objects.all()
    serializer_class = ProfileDetailSerializer
    lookup_field = "username"
    lookup_url_kwarg = "user_name"

    def retrieve(self, request, *args, **kwargs):
        has_full_access = bool(request.auth)

        try:
            instance = self.get_object()
            # update the instance's sync IDs
            ExternalSync.sync(profile=instance)

        except Http404:
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_USER_NOT_FOUND
            )
            return Response(meta, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        data = serializer.data

        return Response(
            {
                "results": data,
            },
            status=status.HTTP_200_OK,
        )


class MultipleFieldLookupMixin:
    """
    Allows us to lookup by different field names
    """

    def get_object(self):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        queryset_filter = {}

        for field in self.lookup_fields:
            if self.kwargs.get(field, None):
                queryset_filter[field] = self.kwargs[field]

        obj = get_object_or_404(queryset, **queryset_filter)
        self.check_object_permissions(self.request, obj)
        return obj


class GroupDetailView(MultipleFieldLookupMixin, generics.RetrieveAPIView):
    """
    Retrieve a profile
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]
    queryset = WpBpGroup.objects.all()
    serializer_class = GroupDetailSerializer
    lookup_fields = ["pk", "slug"]
    lookup_url_kwarg = ["pk"]

    def retrieve(self, request, *args, **kwargs):
        has_full_access = bool(request.auth)

        try:
            instance: WpBpGroup = self.get_object()

            if instance.status != "public" and not has_full_access:
                meta = build_metadata(
                    has_full_access, error=RESTError.FATAL_GROUP_NOT_FOUND
                )
                return Response(meta, status=status.HTTP_404_NOT_FOUND)

        except Http404:
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_GROUP_NOT_FOUND
            )
            return Response(meta, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        data = serializer.data

        return Response(
            {
                "results": data,
            },
            status=status.HTTP_200_OK,
        )


class TokenPutView(generics.CreateAPIView):
    """
    Update a token for an app
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    serializer_class = TokenSerializer


class LogoutView(generics.CreateAPIView):
    """
    Log a user out
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    serializer_class = LogoutSerializer

    @swagger_auto_schema(
        request_body=LogoutSerializer,
        responses={
            200: openapi.Response(
                "Success",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "user_name": openapi.Schema(
                                    type=openapi.TYPE_STRING
                                ),
                                "user_agent": openapi.Schema(
                                    type=openapi.TYPE_STRING
                                ),
                                "url": openapi.Schema(
                                    type=openapi.TYPE_STRING
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: "Validation error",
            401: "Unauthorized",
        },
    )
    def post(self, request, *args, **kwargs):
        # should always be true
        has_full_access = bool(self.request.auth)

        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)

            app_logout(
                request=self.request,
                redirect_behaviour=RedirectBehaviour.NO_REDIRECT,
                user_name=serializer.validated_data.get("user_name"),
                user_agent=serializer.validated_data.get("user_agent"),
            )

            # send the logout request to all endpoints
            logout_all_endpoints_sync()

            return Response(
                {
                    "message": "Action successfully triggered.",
                    "data": {
                        "user": {
                            "user": serializer.validated_data.get("user_name"),
                            "url": reverse(
                                "profiles_detail_view",
                                args=[
                                    serializer.validated_data.get("user_name")
                                ],
                            ),
                        },
                        "user_agent": serializer.validated_data.get(
                            "user_agent"
                        ),
                        "app": settings.CILOGON_APP_LIST,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            message = f"Validation error in logout: {e}"
            logger.warning(message)

            return Response(
                {
                    "error": "Validation failed",
                    "details": e.detail if hasattr(e, "detail") else str(e),
                    **build_metadata(
                        has_full_access, error=RESTError.FATAL_UNDEFINED_ERROR
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            message = f"Unexpected error in logout: {e}"
            logger.exception(message)

            return Response(
                {
                    "error": "An unexpected error occurred",
                    **build_metadata(
                        has_full_access, error=RESTError.FATAL_UNDEFINED_ERROR
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
