"""
Tests for duplicate profile prevention (issue #486).

Verifies:
- Profile.username has a unique constraint at the database level
- API _deduplicate_profiles method picks the most complete record
- get_or_create is used instead of create for profile creation paths
- The deduplication migration logic works correctly
"""

import importlib
from unittest.mock import MagicMock
from unittest.mock import patch

from django.db import IntegrityError
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    ProfileFactory,
)
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    UserFactory,
)
from knowledge_commons_profiles.newprofile.utils import (
    profile_exists_or_has_been_created,
)

_migration_mod = importlib.import_module(
    "knowledge_commons_profiles.newprofile.migrations"
    ".0051_deduplicate_profile_usernames"
)
count_non_empty_fields = _migration_mod.count_non_empty_fields


class ProfileUsernameUniquenessTests(TestCase):
    """Test that the Profile model enforces unique usernames."""

    def test_unique_constraint_prevents_duplicate_usernames(self):
        """Creating two profiles with the same username raises
        IntegrityError."""
        ProfileFactory(username="testuser")
        with self.assertRaises(IntegrityError):
            Profile.objects.create(username="testuser")

    def test_different_usernames_allowed(self):
        """Two profiles with different usernames can coexist."""
        p1 = ProfileFactory(username="user_one")
        p2 = ProfileFactory(username="user_two")
        self.assertNotEqual(p1.pk, p2.pk)


class APIProfileDeduplicationTests(TestCase):
    """Test that the API _deduplicate_profiles method works correctly."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory(username="dupeuser")

    def test_deduplicate_keeps_most_complete_profile(self):
        """_deduplicate_profiles keeps the record with more fields."""
        empty_profile = MagicMock(
            id=1, name="", title="", email="", orcid="",
            twitter="", github="", mastodon="", affiliation="",
        )
        full_profile = MagicMock(
            id=2, name="Full Name", title="Professor",
            email="full@example.com", orcid="0000-0001",
            twitter="", github="testuser", mastodon="", affiliation="MIT",
        )

        request = self.factory.get("/profile/dupeuser")
        request.user = self.user
        api = API(request=request, user=self.user)

        with patch.object(Profile.objects, "filter") as mock_filter:
            mock_qs = MagicMock()
            mock_qs.order_by.return_value = [empty_profile, full_profile]
            mock_filter.return_value = mock_qs

            result = api._deduplicate_profiles()

        self.assertEqual(result, full_profile)
        empty_profile.delete.assert_called_once()

    def test_profile_property_catches_multiple_objects_returned(self):
        """The profile property handles MultipleObjectsReturned."""
        request = self.factory.get("/profile/dupeuser")
        request.user = self.user
        api = API(request=request, user=self.user)
        api._profile = None

        mock_profile = MagicMock()
        with (
            patch.object(
                Profile.objects, "prefetch_related",
            ) as mock_prefetch,
            patch.object(
                api, "_deduplicate_profiles",
                return_value=mock_profile,
            ),
        ):
            mock_prefetch.return_value.get.side_effect = (
                Profile.MultipleObjectsReturned
            )
            result = api.profile

        self.assertEqual(result, mock_profile)


class ProfileCreationGetOrCreateTests(TestCase):
    """Test that profile creation paths use get_or_create."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch("knowledge_commons_profiles.newprofile.utils.WpUser.objects")
    def test_utils_does_not_create_duplicate(self, mock_wp_user_objects):
        """profile_exists_or_has_been_created should not create duplicates."""
        ProfileFactory(username="existing_wp_user")

        mock_wp_user = mock_wp_user_objects.filter.return_value.first
        mock_wp_user.return_value = type(
            "WpUser", (), {"user_login": "existing_wp_user"}
        )()

        result = profile_exists_or_has_been_created("existing_wp_user")
        self.assertTrue(result)
        self.assertEqual(
            Profile.objects.filter(username="existing_wp_user").count(), 1
        )

    def test_api_profile_does_not_create_duplicate(self):
        """API profile property should not create duplicates."""
        user = UserFactory(username="apiuser")
        ProfileFactory(username="apiuser")

        request = self.factory.get("/profile/apiuser")
        request.user = user

        api = API(request=request, user=user)
        profile = api.profile

        self.assertEqual(profile.username, "apiuser")
        self.assertEqual(
            Profile.objects.filter(username="apiuser").count(), 1
        )


class DeduplicateMigrationTests(TestCase):
    """Test the data migration deduplication logic."""

    def test_count_non_empty_fields(self):
        """count_non_empty_fields counts populated fields correctly."""
        profile = ProfileFactory(
            name="Test",
            email="test@example.com",
            title="Prof",
        )
        count = count_non_empty_fields(profile)
        self.assertGreaterEqual(count, 3)

    def test_count_non_empty_fields_empty_profile(self):
        """count_non_empty_fields returns 0 for empty profile."""
        profile = Profile(username="empty")
        count = count_non_empty_fields(profile)
        self.assertEqual(count, 0)
