"""
Tests for reserved-username matching and its enforcement during signup.
"""

from __future__ import annotations

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.models import ReservedUsername
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    get_reserved_patterns,
)
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    username_is_reserved,
)
from knowledge_commons_profiles.cilogon.views import validate_form
from knowledge_commons_profiles.newprofile.models import Profile


class UsernameIsReservedTests(TestCase):
    """The pure matcher: no database, behaviour only."""

    def test_exact_term_blocks_exact_username(self):
        self.assertTrue(username_is_reserved("admin", ["admin"]))

    def test_prefix_match_blocks_trailing_characters(self):
        # A bare term blocks anything that begins with it.
        self.assertTrue(username_is_reserved("admin123", ["admin"]))
        self.assertTrue(username_is_reserved("administrator", ["admin"]))

    def test_prefix_match_does_not_block_embedded_word(self):
        # "badminton" begins with "bad", not "admin".
        self.assertFalse(username_is_reserved("badminton", ["admin"]))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(username_is_reserved("ADMIN", ["admin"]))
        self.assertTrue(username_is_reserved("admin", ["ADMIN"]))

    def test_separators_are_ignored(self):
        # One entry catches every separator permutation.
        for candidate in [
            "knowledge_commons",
            "knowledge-commons",
            "knowledgeCommons",
            "knowledge_commons_2024",
        ]:
            self.assertTrue(
                username_is_reserved(candidate, ["knowledgecommons"]),
                msg=candidate,
            )

    def test_term_with_separators_also_matches(self):
        # An admin who types the underscored form still works.
        self.assertTrue(
            username_is_reserved("techsupport", ["tech_support"])
        )

    def test_leading_and_trailing_wildcards_match_anywhere(self):
        self.assertTrue(username_is_reserved("techsupport", ["*support*"]))
        self.assertTrue(username_is_reserved("mysupportbot", ["*support*"]))

    def test_ordinary_username_is_not_reserved(self):
        self.assertFalse(
            username_is_reserved("martineve", ["admin", "knowledgecommons"])
        )

    def test_empty_pattern_list_blocks_nothing(self):
        self.assertFalse(username_is_reserved("admin", []))

    def test_first_matching_pattern_wins(self):
        self.assertTrue(
            username_is_reserved("superuser1", ["admin", "superuser"])
        )


class GetReservedPatternsTests(TestCase):
    """Only active rows are used for matching."""

    def test_returns_only_active_patterns(self):
        # Use terms not present in the seed data so the assertions are
        # independent of whatever the shipped list happens to contain.
        ReservedUsername.objects.create(pattern="zzactiveterm", active=True)
        ReservedUsername.objects.create(pattern="zzinactiveterm", active=False)

        patterns = get_reserved_patterns()

        self.assertIn("zzactiveterm", patterns)
        self.assertNotIn("zzinactiveterm", patterns)


class ValidateFormReservedUsernameTests(TestCase):
    """The signup form rejects reserved usernames with a polite message."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.post("/register/")
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        return request

    def _messages(self, request):
        return [str(m) for m in request._messages]

    def test_reserved_username_is_rejected(self):
        ReservedUsername.objects.create(pattern="zzreserved", active=True)

        request = self._request()
        errored = validate_form(
            "new@example.com", "New User", request, "zzreserved99"
        )

        self.assertTrue(errored)

    def test_inactive_reserved_term_does_not_block(self):
        ReservedUsername.objects.create(pattern="zzreserved", active=False)

        request = self._request()
        errored = validate_form(
            "new@example.com", "New User", request, "zzreserved99"
        )

        self.assertFalse(errored)

    def test_allowed_username_passes(self):
        ReservedUsername.objects.create(pattern="zzreserved", active=True)

        request = self._request()
        errored = validate_form(
            "new@example.com", "New User", request, "martineve"
        )

        self.assertFalse(errored)

    def test_reserved_username_creates_no_profile(self):
        ReservedUsername.objects.create(pattern="zzreserved", active=True)

        request = self._request()
        validate_form("new@example.com", "New User", request, "zzreserved99")

        self.assertFalse(
            Profile.objects.filter(username="zzreserved99").exists()
        )
