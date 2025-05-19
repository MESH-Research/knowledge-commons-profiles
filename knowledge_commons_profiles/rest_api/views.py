"""
The REST API for the profile app
"""

import logging

from django.http import Http404
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from knowledge_commons_profiles.cilogon.models import SubAssociation
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
from knowledge_commons_profiles.rest_api.serializers import (
    ProfileDetailSerializer,
)
from knowledge_commons_profiles.rest_api.serializers import ProfileSerializer
from knowledge_commons_profiles.rest_api.serializers import SubProfileSerializer
from knowledge_commons_profiles.rest_api.serializers import TokenSerializer
from knowledge_commons_profiles.rest_api.utils import build_metadata

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
        except Http404:
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_USER_NOT_FOUND
            )
            return Response(meta, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        data = serializer.data
        meta = build_metadata(has_full_access)

        return Response({"data": data, **meta}, status=status.HTTP_200_OK)


class GroupDetailView(generics.RetrieveAPIView):
    """
    Retrieve a Group
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]
    serializer_class = GroupDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "pk"
    request = None

    def get_object(self, *args, **kwargs):
        self.api = API(self.request, None, use_wordpress=True)
        has_full_access = bool(self.request.auth)

        # build the access level for group permissions
        # it's either "public" or all the others
        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        pk = kwargs.get("pk")
        slug = kwargs.get("slug")

        if not pk and not slug:
            raise ValueError

        return self.api.get_group(
            group_id=pk,
            slug=slug,
            status_choices=group_status,
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a group

        """
        self.request = request
        has_full_access = bool(self.request.auth)

        try:
            instance = self.get_object(*args, **kwargs)
        except (Http404, WpBpGroup.DoesNotExist):
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_GROUP_NOT_FOUND
            )
            return Response(meta, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            meta = build_metadata(
                has_full_access, error=RESTError.FATAL_NO_GROUP_ID_OR_SLUG
            )
            return Response(meta, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(instance)
        data = serializer.data
        meta = build_metadata(has_full_access)

        return Response({"data": data, **meta}, status=status.HTTP_200_OK)


class TokenPutView(generics.CreateAPIView):
    """
    Update a token for an app
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]
    serializer_class = TokenSerializer
