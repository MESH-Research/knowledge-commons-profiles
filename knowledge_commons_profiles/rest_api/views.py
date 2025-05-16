"""
The REST API for the profile app
"""

import logging

import sentry_sdk
from django.db import OperationalError
from django.http import Http404
from nameparser import HumanName
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.api import ErrorModel
from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.rest_api.authentication import (
    StaticBearerAuthentication,
)
from knowledge_commons_profiles.rest_api.errors import RESTError
from knowledge_commons_profiles.rest_api.serializers import (
    GroupMembershipSerializer,
)
from knowledge_commons_profiles.rest_api.timer import get_elapsed
from knowledge_commons_profiles.rest_api.timer import rest_timer

logger = logging.getLogger(__name__)


def build_metadata(authed, error=None):
    """
    Build the metadata for the response
    """

    return_dict = {
        "meta": {
            "authorized": authed,
            "elapsed": get_elapsed(),
        }
    }

    if error:
        return_dict["meta"]["error"] = error

    return return_dict


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
        """

        non_fatal_error = None

        has_full_access = bool(request.auth)
        user = kw.get("user_name")

        if not user:
            return Response(
                build_metadata(
                    has_full_access, error=RESTError.FATAL_NO_USERNAME_DEFINED
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # build the API object
        if not self.api:
            self.api = API(request, user, use_wordpress=True)

        # get the profile: triggers MySQL access
        try:
            profile_info_obj = self.api.get_profile_info()
        except Http404:
            return Response(
                build_metadata(
                    has_full_access, error=RESTError.FATAL_USER_NOT_FOUND
                ),
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:  # noqa: BLE001
            sentry_sdk.capture_exception(exc)

            return Response(
                build_metadata(
                    has_full_access, error=RESTError.FATAL_UNDEFINED_ERROR
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # format the name into components
        # NOTE: we want to harmonise this with Works's name parser
        # TODO: harmonize with Works
        name_object = HumanName(profile_info_obj["name"])

        # build the access level for group permissions
        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        # serialize the groups for the user
        groups, error = self.api.get_groups(
            status_choices=group_status, on_error=ErrorModel.RETURN
        )

        if error:
            if isinstance(error, OperationalError):
                non_fatal_error = (
                    RESTError.NON_FATAL_NO_MYSQL_SILENT_FIELDS_MISSING
                )
            else:
                non_fatal_error = RESTError.NON_FATAL_UNDEFINED_ERROR

        serialized_groups = GroupMembershipSerializer(
            groups,
            many=True,
            context={"request": request},
        )

        # Note that email is confidential
        # Only groups that are "public" will be shown by default unless authed
        context = {
            "data": {
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
            }
        }
        context.update(build_metadata(has_full_access, error=non_fatal_error))

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

    @rest_timer
    def get(self, request, *args, **kw):
        """
        Return a JSON response containing the group's information,
        """

        has_full_access = bool(request.auth)

        group_id = kw.get("pk")
        slug = kw.get("slug")

        if not group_id and not slug:
            return Response(
                build_metadata(
                    has_full_access, error=RESTError.FATAL_NO_GROUP_ID_OR_SLUG
                ),
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
            context = {
                "data": self.api.get_group(
                    group_id=group_id,
                    slug=slug,
                    status_choices=group_status,
                ),
            }
            context.update(build_metadata(has_full_access))

            return Response(context, status=status.HTTP_200_OK)
        except WpBpGroup.DoesNotExist:
            return Response(
                build_metadata(
                    has_full_access, error=RESTError.FATAL_GROUP_NOT_FOUND
                ),
                status=status.HTTP_404_NOT_FOUND,
            )
        except OperationalError as oe:
            logger.warning(
                "Unable to connect to MySQL, fast-failing group data."
            )

            sentry_sdk.capture_exception(oe)

            return Response(
                build_metadata(
                    has_full_access,
                    error=RESTError.NON_FATAL_NO_MYSQL_SILENT_FIELDS_MISSING,
                ),
                status=status.HTTP_200_OK,
            )
