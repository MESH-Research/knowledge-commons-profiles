"""
The REST API for the profile app
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.urls import reverse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.views import RedirectBehaviour
from knowledge_commons_profiles.cilogon.views import app_logout
from knowledge_commons_profiles.newprofile.api import API
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
from knowledge_commons_profiles.rest_api.serializers import (
    GroupDetailSerializer,
)
from knowledge_commons_profiles.rest_api.serializers import LogoutSerializer
from knowledge_commons_profiles.rest_api.serializers import (
    ProfileDetailSerializer,
)
from knowledge_commons_profiles.rest_api.serializers import ProfileSerializer
from knowledge_commons_profiles.rest_api.serializers import SubProfileSerializer
from knowledge_commons_profiles.rest_api.serializers import TokenSerializer
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


class ProfileListView(generics.ListAPIView):
    """
    List all profiles
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]
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


class GroupDetailView(APIView):
    """
    Retrieve a Group with improved error handling
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]

    def get_object(
        self,
        request: Request,
        pk: str | None = None,
        slug: str | None = None,
    ):
        """Get group object with proper error handling"""
        api = API(request, None, use_wordpress=True)
        has_full_access = bool(request.auth)

        # Build access level - restrict to public if no auth
        group_status = WpBpGroup.STATUS_CHOICES if has_full_access else None

        if not pk and not slug:
            message = "Either 'pk' or 'slug' must be provided"
            raise ValidationError(message)

        return api.get_group(
            group_id=pk,
            slug=slug,
            status_choices=group_status,
        )

    def get(
        self,
        request: Request,
        pk: str | None = None,
        slug: str | None = None,
    ) -> Response:
        """Enhanced retrieve method"""
        has_full_access = bool(request.auth)

        try:
            instance = self.get_object(request, pk, slug)
        except (Http404, WpBpGroup.DoesNotExist):
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_GROUP_NOT_FOUND
            )
            return Response(meta, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_NO_GROUP_ID_OR_SLUG
            )
            return Response(
                {**meta, "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            message = f"Unexpected error retrieving group: {e}"
            logger.exception(message)
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_UNDEFINED_ERROR
            )
            return Response(meta, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = GroupDetailSerializer(
            instance, context={"request": request}
        )
        return Response(
            {"results": serializer.data},
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
