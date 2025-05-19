"""
Serializers for the REST API

"""

from nameparser import HumanName
from rest_framework import serializers
from rest_framework.reverse import reverse

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpBpGroup


class GroupMembershipSerializer(serializers.Serializer):
    """
    Serializer for the GroupMembership model
    """

    id = serializers.IntegerField()
    group_name = serializers.CharField()
    role = serializers.CharField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        """
        Build the URL for the group's API view
        """
        # obj is a dict { "id": ..., "group_name": ..., "role": ... }
        request = self.context.get("request")
        return reverse("groups_detail_view", args=[obj["id"]], request=request)


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
            logged_in = bool(kwargs["context"]["request"].auth)
        except KeyError:
            logged_in = False

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
            "url",
        ]

    def get_url(self, obj):
        """
        Build the URL for the group's API view
        """
        # obj is a dict { "id": ..., "group_name": ..., "role": ... }
        request = self.context.get("request")
        return reverse(
            "profiles_detail_view", args=[obj.username], request=request
        )

    def get_first_name(self, obj):
        """
        Formats the first name
        """
        name = HumanName(obj.name or "")

        # include middle if present
        parts = [name.first, name.middle]
        return " ".join(p for p in parts if p)

    def get_last_name(self, obj):
        """
        Formats the last name
        """
        return HumanName(obj.name or "").last


class ProfileDetailSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    institutional_affiliation = serializers.CharField(
        source="institutional_or_other_affiliation", allow_blank=True
    )
    academic_interests = AcademicInterestSerializer(many=True, read_only=True)
    groups = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Don't return emails when listing users
        request = self._kwargs.get("context", {}).get("request")

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
        ]

    def get_groups(self, obj):
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
        name = HumanName(obj.name or "")
        parts = [name.first, name.middle]
        return " ".join(p for p in parts if p)

    def get_last_name(self, obj):
        return HumanName(obj.name or "").last


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
