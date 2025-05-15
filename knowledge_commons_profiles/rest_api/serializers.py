"""
Serializers for the REST API

"""

from rest_framework import serializers
from rest_framework.reverse import reverse


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
        return reverse("group_rest_view", args=[obj["id"]], request=request)
