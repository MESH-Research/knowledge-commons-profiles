"""
The REST API for the profile app
"""

import logging

import sentry_sdk
from django.db import OperationalError
from nameparser import HumanName
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.rest_api.authentication import (
    StaticBearerAuthentication,
)
from knowledge_commons_profiles.rest_api.serializers import (
    GroupMembershipSerializer,
)
from knowledge_commons_profiles.rest_api.timer import get_elapsed
from knowledge_commons_profiles.rest_api.timer import rest_timer

logger = logging.getLogger(__name__)


class ProfileView(APIView):
    """
    A REST view for retrieving user profile information
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]  # allow both token & anon
    api = None

    @rest_timer
    def get(self, request, *args, **kw):
        """
        Return a JSON response containing the user's profile information.

        The response is returned with a status of 200 OK.
        """

        has_full_access = bool(request.auth)

        user = kw.get("user_name")

        if not user:
            return Response(
                {
                    "error": "No user name provided",
                    "authorized": has_full_access,
                    "elapsed": get_elapsed(),
                },
                status=status.HTTP_200_OK,
            )

        # build the API object
        if not self.api:
            self.api = API(request, user, use_wordpress=True)

        # get the profile: triggers MySQL access
        profile_info_obj = self.api.get_profile_info()

        # format the name into components
        # NOTE: we want to harmonise this with Works's name parser
        # TODO: harmonize with Works
        name_object = HumanName(profile_info_obj["name"])

        # build the access level for group permissions
        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        # serialize the groups for the user
        serialized_groups = GroupMembershipSerializer(
            self.api.get_groups(status_choices=group_status),
            many=True,
            context={"request": request},
        )

        # Note that email is confidential
        # Only groups that are "public" will be shown by default unless authed
        context = {
            "hits": {
                "username": profile_info_obj["username"],
                "email": profile_info_obj["email"] if has_full_access else "",
                "name": name_object.full_name,
                "first_name": name_object.first + " " + name_object.middle,
                "last_name": name_object.last,
                "institutional_affiliation": profile_info_obj[
                    "institutional_or_other_affiliation"
                ],
                "orcid": profile_info_obj["orcid"],
                "groups": serialized_groups.data,
            },
            "authorized": has_full_access,
            "elapsed": get_elapsed(),
        }

        return Response(
            context,
            status=status.HTTP_200_OK,
        )


class GroupView(APIView):
    """
    A REST view for retrieving group information
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]  # allow both token & anon
    api = None

    def get(self, request, *args, **kw):
        """
        Return a JSON response containing the group's information,

        The response is returned with a status of 200 OK.
        """

        has_full_access = bool(request.auth)

        group_id = kw.get("pk")
        slug = kw.get("slug")

        if not group_id and not slug:
            return Response(
                {
                    "error": "No group ID or slug provided",
                    "authorized": has_full_access,
                    "elapsed": get_elapsed(),
                },
                status=status.HTTP_200_OK,
            )

        # create a skeleton API object
        if not self.api:
            self.api = API(request, None, use_wordpress=True)

        # build the access level for group permissions
        # it's either "public" or all the others
        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        # Note that only groups that are "public" will be shown by default
        # unless authed. Users with the static bearer key can see all groups.
        try:
            return Response(
                {
                    "hits": self.api.get_group(
                        group_id=group_id,
                        slug=slug,
                        status_choices=group_status,
                    ),
                    "authorized": has_full_access,
                    "elapsed": get_elapsed(),
                },
                status=status.HTTP_200_OK,
            )
        except OperationalError as oe:
            logger.warning(
                "Unable to connect to MySQL, fast-failing group data."
            )

            sentry_sdk.capture_exception(oe)

            return Response(
                {
                    "Error": "Unable to connect to database.",
                    "authorized": has_full_access,
                    "elapsed": get_elapsed(),
                },
                status=status.HTTP_200_OK,
            )
