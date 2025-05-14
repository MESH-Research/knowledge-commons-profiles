"""
The REST API for the profile app
"""

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


class ProfileView(APIView):
    """
    A REST view for retrieving user profile information
    """

    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [AllowAny]  # allow both token & anon
    api = None

    def get(self, request, *args, **kw):
        """
        Return a JSON response containing the user's profile information,
        academic interests, education, a short string about the user,
        their latest blog posts, their latest Mastodon posts (if they have
        a Mastodon account), and a string representing their works.

        The response is returned with a status of 200 OK.
        """

        has_full_access = bool(request.auth)

        user = kw.get("user_name")

        if not user:
            return Response(
                {},
                status=status.HTTP_200_OK,
                headers={"Is-Authorized": has_full_access},
            )

        if not self.api:
            self.api = API(request, user, use_wordpress=True)

        profile_info_obj = self.api.get_profile_info()

        # format the name into components
        name_object = HumanName(profile_info_obj["name"])

        # build the access level for group permissions
        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        context = {
            "username": profile_info_obj["username"],
            "email": profile_info_obj["email"],
            "name": name_object.full_name,
            "first_name": name_object.first + " " + name_object.middle,
            "last_name": name_object.last,
            "institutional_affiliation": profile_info_obj[
                "institutional_or_other_affiliation"
            ],
            "orcid": profile_info_obj["orcid"],
            "groups": self.api.get_groups(status_choices=group_status),
        }

        return Response(
            context,
            status=status.HTTP_200_OK,
            headers={"Is-Authorized": has_full_access},
        )
