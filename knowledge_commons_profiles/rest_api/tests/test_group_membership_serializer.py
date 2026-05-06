"""
Tests for GroupMembershipSerializer's inviter resolution.

These guard against the n+1 in /api/v1/subs/ where get_inviter
previously hit the wp_users table once per group membership
(see issue #554).
"""

from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.rest_api.serializers.serializers import (
    GroupMembershipSerializer,
)


class GetInviterUsesPrefetchedUsername(TestCase):
    """get_inviter must read inviter_username from the dict, not query."""

    def test_returns_reversed_url_from_prefetched_username(self):
        serializer = GroupMembershipSerializer()
        obj = {
            "id": 1,
            "group_name": "Test Group",
            "role": "member",
            "slug": "test-group",
            "status": "public",
            "avatar": "",
            "inviter_id": 42,
            "inviter_username": "martin_eve",
        }

        self.assertEqual(
            serializer.get_inviter(obj),
            reverse("profiles_detail_view", args=["martin_eve"]),
        )

    def test_returns_none_when_inviter_username_is_none(self):
        serializer = GroupMembershipSerializer()
        obj = {
            "id": 1,
            "group_name": "Test Group",
            "role": "member",
            "slug": "test-group",
            "status": "public",
            "avatar": "",
            "inviter_id": 0,
            "inviter_username": None,
        }

        self.assertIsNone(serializer.get_inviter(obj))

    def test_returns_none_when_inviter_username_key_missing(self):
        serializer = GroupMembershipSerializer()
        obj = {
            "id": 1,
            "group_name": "Test Group",
            "role": "member",
            "slug": "test-group",
            "status": "public",
            "avatar": "",
            "inviter_id": 42,
        }

        self.assertIsNone(serializer.get_inviter(obj))
