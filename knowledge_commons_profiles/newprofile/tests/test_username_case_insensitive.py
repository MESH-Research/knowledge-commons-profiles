"""Tests for case-insensitive ``Profile.username`` uniqueness and lookups.

These exercise the database-level behaviour delivered by converting the
``username`` column to PostgreSQL's ``citext`` type: a case-insensitive match
is a uniqueness conflict, lookups resolve regardless of casing, and the stored
value keeps its original casing.
"""

from unittest.mock import MagicMock

from django.contrib.messages import get_messages
from django.contrib.messages.storage.session import SessionStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError
from django.db import transaction
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.views import validate_form
from knowledge_commons_profiles.newprofile.models import Profile


class UsernameCaseInsensitiveUniquenessTests(TestCase):
    """A case-insensitive username clash is treated as a conflict."""

    def test_case_insensitive_duplicate_insert_is_rejected(self):
        Profile.objects.create(username="alice", name="Alice")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(username="Alice", name="Alice Two")

    def test_get_or_create_returns_existing_for_case_variant(self):
        original = Profile.objects.create(username="alice", name="Alice")

        obj, created = Profile.objects.get_or_create(
            username="ALICE", defaults={"name": "Should Not Be Used"}
        )

        self.assertFalse(created)
        self.assertEqual(obj.pk, original.pk)

    def test_stored_value_preserves_original_case(self):
        Profile.objects.create(username="MixedCase", name="Mixed")

        stored = Profile.objects.get(username="mixedcase")
        self.assertEqual(stored.username, "MixedCase")


class UsernameCaseInsensitiveLookupTests(TestCase):
    """Lookups resolve regardless of the casing supplied."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="alice", name="Alice"
        )

    def test_get_resolves_case_insensitively(self):
        self.assertEqual(
            Profile.objects.get(username="ALICE").pk, self.profile.pk
        )

    def test_filter_matches_case_insensitively(self):
        self.assertTrue(
            Profile.objects.filter(username="aLiCe").exists()
        )

    def test_icontains_search_still_works(self):
        # The members search relies on ``username__icontains`` (ILIKE);
        # this must keep working after the column type change.
        self.assertTrue(
            Profile.objects.filter(username__icontains="LIC").exists()
        )

    def test_ordering_comparison_still_works(self):
        # Cursor pagination in the members view compares with ``__lt``.
        results = list(
            Profile.objects.filter(username__lt="m").order_by("username")
        )
        self.assertIn(self.profile.pk, [p.pk for p in results])


class ValidateFormCaseInsensitiveUsernameTests(TestCase):
    """Registration rejects a username that clashes case-insensitively."""

    def setUp(self):
        self.factory = RequestFactory()
        Profile.objects.create(username="alice", name="Alice")

    def _create_request(self):
        request = self.factory.post("/register/")
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        request._messages = SessionStorage(request)
        return request

    def test_case_variant_username_is_flagged_as_existing(self):
        request = self._create_request()

        errored = validate_form(
            "brand-new@example.com", "Alice Two", request, "Alice"
        )

        self.assertTrue(errored)
        self.assertIn(
            "This username already exists",
            [str(m) for m in get_messages(request)],
        )
