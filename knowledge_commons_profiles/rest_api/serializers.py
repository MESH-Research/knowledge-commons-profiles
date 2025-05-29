"""
Serializers for the REST API

"""

import json
import logging
from typing import Any

from rest_framework import serializers
from rest_framework.reverse import reverse

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.rest_api import utils

logger = logging.getLogger(__name__)


class GroupMembershipSerializer(serializers.Serializer):
    """
    Serializer for the GroupMembership model
    """

    id = serializers.IntegerField()
    group_name = serializers.CharField()
    role = serializers.CharField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj: dict[str, Any]) -> str:
        """
        Build the URL for the group's API view

        Args:
            obj: Dict containing group data with keys: id, group_name, role
        """
        request = self.context.get("request")
        if not request:
            return ""

        try:
            return reverse(
                "groups_detail_view", args=[obj["id"]], request=request
            )
        except Exception as e:  # noqa: BLE001
            message = (
                f"Failed to build group URL for group {obj.get('id')}: {e}"
            )
            logger.warning(message)
            return ""


class GroupDetailSerializer(serializers.Serializer):
    """
    Serializer for the Group model
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    visibility = serializers.CharField()
    description = serializers.CharField()
    avatar = serializers.CharField()
    groupblog = serializers.CharField()
    upload_roles = serializers.CharField()
    moderate_roles = serializers.CharField()


class AcademicInterestSerializer(serializers.ModelSerializer):

    class Meta:
        model = AcademicInterest
        fields = ["id", "text"]


class ProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    institutional_affiliation = serializers.CharField(
        source="institutional_or_other_affiliation", allow_blank=True
    )
    academic_interests = AcademicInterestSerializer(many=True, read_only=True)
    url = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Don't return emails when listing users
        try:
            request = self.context.get("request")
            logged_in = bool(request and request.auth)
        except (KeyError, AttributeError):
            logged_in = False

        if not logged_in and "email" in self.fields:
            del self.fields["email"]

        super().__init__(*args, **kwargs)

    class Meta:
        model = Profile
        fields = [
            "username",
            "email",
            "name",
            "first_name",
            "last_name",
            "institutional_affiliation",
            "orcid",
            "academic_interests",
            "url",
        ]

    def get_url(self, obj: Profile) -> str:
        """Build the URL for the profile's API view"""
        request = self.context.get("request")
        if not request:
            return ""

        try:
            return reverse(
                "profiles_detail_view", args=[obj.username], request=request
            )
        except Exception as e:  # noqa: BLE001
            message = f"Failed to build profile URL for {obj.username}: {e}"
            logger.warning(message)
            return ""

    def get_first_name(self, obj: Profile) -> str:
        """Extract and format the first name"""
        return utils.get_first_name(obj, logger)

    def get_last_name(self, obj: Profile) -> str:
        """Extract and format the last name"""
        return utils.get_last_name(obj, logger)


class ProfileDetailSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    institutional_affiliation = serializers.CharField(
        source="institutional_or_other_affiliation", allow_blank=True
    )
    academic_interests = AcademicInterestSerializer(many=True, read_only=True)
    groups = serializers.SerializerMethodField()
    external_sync_memberships = serializers.SerializerMethodField()
    external_group_sync = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Don't return emails when listing users
        request = kwargs.get("context", {}).get("request")

        logged_in = False if not request else bool(request.auth)

        if not logged_in:
            del self.fields["email"]

        super().__init__(*args, **kwargs)

    class Meta:
        model = Profile
        fields = [
            "username",
            "email",
            "name",
            "first_name",
            "last_name",
            "institutional_affiliation",
            "orcid",
            "academic_interests",
            "groups",
            "external_sync_memberships",
            "external_group_sync",
        ]

    def get_external_sync_memberships(self, obj: Profile):
        """
        Check if a user is a member of an external organisation
        """
        if not obj.username:
            return []

        try:
            request = self.context.get("request")
            api = API(request, obj.username, use_wordpress=False)

            # Handle case where is_member_of might be None or empty
            member_data = api.profile.is_member_of
            if not member_data:
                return []

            return json.loads(member_data)
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            message = (
                f"Failed to get external sync memberships "
                f"for {obj.username}: {e}"
            )
            logger.warning(message)
            return []

    def get_external_group_sync(self, obj: Profile):
        """
        Check if a user is a member of an external organisation
        """
        request = self.context.get("request")
        has_full_access = bool(request.auth)

        if not has_full_access:
            return []

        user_id = obj.username
        request = self.context.get("request")

        if not user_id:
            return []

        # create an API object
        api = API(request, user_id, use_wordpress=False)
        return json.loads(api.profile.is_member_of)

    def get_groups(self, obj: Profile) -> list[dict[str, Any]]:
        """
        Query the WP DB for this user's confirmed group memberships,
        then serialize them with your existing GroupMembershipSerializer.
        """
        # assume you store the central user ID on Profile.central_user_id
        user_id = obj.username
        request = self.context.get("request")

        has_full_access = bool(request.auth)

        group_status = (
            None if not has_full_access else WpBpGroup.STATUS_CHOICES
        )

        if not user_id:
            return []

        # create a skeleton API object
        api = API(request, user_id, use_wordpress=True)

        # serialize into the same shape you already have
        return GroupMembershipSerializer(
            api.get_groups(
                status_choices=group_status,
            ),
            many=True,
            context=self.context,
        ).data

    def get_first_name(self, obj):
        return utils.get_first_name(obj, logger)

    def get_last_name(self, obj):
        return utils.get_last_name(obj, logger)


class SubProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the SubAssociation model
    """

    profile = ProfileSerializer()
    sub = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = SubAssociation
        fields = ["sub", "profile"]

    def get_fields(self):
        fields = super().get_fields()
        # rebuild 'profile' with the current context
        fields["profile"] = ProfileSerializer(
            context=self.context, read_only=True
        )
        return fields


class TokenSerializer(serializers.ModelSerializer):
    """
    Serializer for the TokenUserAgentAssociations model
    """

    class Meta:
        model = TokenUserAgentAssociations
        fields = "__all__"


class LogoutSerializer(serializers.Serializer):
    """
    Serializer for the Logout view
    """

    user_name = serializers.CharField()
    user_agent = serializers.CharField()

    def validate_user_name(self, value: str) -> str:
        """Validate username format"""
        value = value.strip()
        if not value:
            message = "Username cannot be empty"
            raise serializers.ValidationError(message)
        return value

    def validate_user_agent(self, value: str) -> str:
        """Validate user agent string"""
        value = value.strip()
        if not value:
            message = "User agent cannot be empty"
            raise serializers.ValidationError(message)
        return value
