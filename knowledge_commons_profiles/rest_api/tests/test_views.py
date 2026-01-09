"""
Tests for REST API views.
"""

from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.views import SubSingleView


class TestSubSingleViewQueryset(TestCase):
    """Tests for the SubSingleView queryset filtering."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        # Create two profiles
        self.profile1 = Profile.objects.create(
            username="martin_eve",
            name="Martin Eve",
        )
        self.profile2 = Profile.objects.create(
            username="mikethicke",
            name="Mike Thicke",
        )

        # Create SubAssociations for profile1
        self.sub1_profile1 = SubAssociation.objects.create(
            profile=self.profile1,
            sub="http://cilogon.org/serverA/users/12345",
        )
        self.sub2_profile1 = SubAssociation.objects.create(
            profile=self.profile1,
            sub="http://cilogon.org/serverB/users/67890",
        )

        # Create SubAssociations for profile2
        self.sub1_profile2 = SubAssociation.objects.create(
            profile=self.profile2,
            sub="http://cilogon.org/serverC/users/11111",
        )

    def _get_queryset_for_username(self, username):
        """Get the queryset returned by SubSingleView for a given username."""
        request = self.factory.get(f"/api/v1/subs/{username}/")
        view = SubSingleView()
        view.request = request
        view.kwargs = {"username": username}
        return view.get_queryset()

    def test_returns_only_subs_for_requested_user(self):
        """Test that only subs for the requested username are returned."""
        queryset = self._get_queryset_for_username("martin_eve")

        # Should return exactly 2 subs for martin_eve
        self.assertEqual(queryset.count(), 2)

        # Verify all returned subs belong to martin_eve
        for sub_assoc in queryset:
            self.assertEqual(sub_assoc.profile.username, "martin_eve")

    def test_does_not_return_other_users_subs(self):
        """Test that subs for other users are NOT returned."""
        queryset = self._get_queryset_for_username("martin_eve")

        # Verify mikethicke's subs are NOT in the results
        returned_subs = set(queryset.values_list("sub", flat=True))
        self.assertIn("http://cilogon.org/serverA/users/12345", returned_subs)
        self.assertIn("http://cilogon.org/serverB/users/67890", returned_subs)
        self.assertNotIn(
            "http://cilogon.org/serverC/users/11111",
            returned_subs,
        )

    def test_returns_correct_subs_for_other_user(self):
        """Test that requesting mikethicke returns only their subs."""
        queryset = self._get_queryset_for_username("mikethicke")

        # Should return exactly 1 sub for mikethicke
        self.assertEqual(queryset.count(), 1)

        sub_assoc = queryset.first()
        self.assertEqual(sub_assoc.profile.username, "mikethicke")
        self.assertEqual(sub_assoc.sub, "http://cilogon.org/serverC/users/11111")

    def test_returns_empty_for_user_with_no_subs(self):
        """Test that a user with no subs returns an empty queryset."""
        # Create a profile with no subs
        Profile.objects.create(
            username="no_subs_user",
            name="No Subs User",
        )

        queryset = self._get_queryset_for_username("no_subs_user")

        self.assertEqual(queryset.count(), 0)

    def test_returns_empty_for_nonexistent_user(self):
        """Test that a nonexistent username returns an empty queryset."""
        queryset = self._get_queryset_for_username("nonexistent_user")

        self.assertEqual(queryset.count(), 0)

    def test_queryset_uses_select_related(self):
        """Test that the queryset uses select_related for profile."""
        queryset = self._get_queryset_for_username("martin_eve")

        # Check that select_related is applied (profile should be in
        # _prefetch_related_lookups)
        # The query should have a JOIN, not separate queries
        self.assertIn(
            "profile",
            queryset.query.select_related,
        )
