"""
Tests for reserved-username matching and its enforcement during signup.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import ReservedUsername
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    get_reserved_patterns,
)
from knowledge_commons_profiles.cilogon.reserved_usernames import import_terms
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    parse_reserved_terms,
)
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    serialize_reserved_terms,
)
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    username_is_reserved,
)
from knowledge_commons_profiles.cilogon.views import register
from knowledge_commons_profiles.cilogon.views import validate_form
from knowledge_commons_profiles.newprofile.models import Profile

# Stable hook the signup template exposes when a reserved username is rejected,
# so tests assert on presence rather than exact wording. The id (not the bare
# class name, which also appears in the page's CSS) uniquely marks the element.
INLINE_WARNING_MARKER = b'id="username-reserved-warning"'


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


class ParseReservedTermsTests(TestCase):
    """Turning pasted text into (pattern, note) pairs."""

    def test_plain_lines_become_patterns_without_notes(self):
        result = parse_reserved_terms("admin\nsuperuser\n")
        self.assertEqual(result, [("admin", ""), ("superuser", "")])

    def test_note_after_pipe_is_captured(self):
        result = parse_reserved_terms("admin | Administrative role")
        self.assertEqual(result, [("admin", "Administrative role")])

    def test_blank_lines_and_comments_are_ignored(self):
        text = "# platform names\nadmin\n\n   \n# more\nsuperuser\n"
        result = parse_reserved_terms(text)
        self.assertEqual(result, [("admin", ""), ("superuser", "")])

    def test_surrounding_whitespace_is_trimmed(self):
        result = parse_reserved_terms("  admin   |   note here  ")
        self.assertEqual(result, [("admin", "note here")])

    def test_later_duplicate_overrides_earlier(self):
        result = parse_reserved_terms("admin | first\nadmin | second")
        self.assertEqual(result, [("admin", "second")])

    def test_empty_text_yields_no_terms(self):
        self.assertEqual(parse_reserved_terms(""), [])


class SerializeReservedTermsTests(TestCase):
    """Rendering (pattern, note) pairs back into pasteable text."""

    def test_terms_without_notes_are_bare_patterns(self):
        text = serialize_reserved_terms([("admin", ""), ("root", "")])
        self.assertEqual(text, "admin\nroot")

    def test_terms_with_notes_use_pipe_separator(self):
        text = serialize_reserved_terms([("admin", "Administrative role")])
        self.assertEqual(text, "admin | Administrative role")

    def test_round_trip_is_stable(self):
        terms = [("admin", "role"), ("knowledgecommons", "")]
        self.assertEqual(
            parse_reserved_terms(serialize_reserved_terms(terms)), terms
        )


class ImportTermsTests(TestCase):
    """Import replaces the whole list with the pasted terms."""

    def _count(self, pattern):
        return ReservedUsername.objects.filter(pattern=pattern)

    def test_pasted_terms_are_created_active_with_notes(self):
        count = import_terms("zzalpha\nzzbeta | a note")

        self.assertEqual(count, 2)
        self.assertTrue(
            ReservedUsername.objects.filter(
                pattern="zzalpha", active=True
            ).exists()
        )
        self.assertEqual(self._count("zzbeta").first().note, "a note")

    def test_import_replaces_the_entire_existing_list(self):
        # Anything already present -- including the seed data -- is removed.
        ReservedUsername.objects.create(pattern="zzdropme")

        import_terms("zzalpha")

        self.assertFalse(self._count("zzdropme").exists())
        self.assertFalse(
            ReservedUsername.objects.filter(pattern="admin").exists()
        )
        self.assertTrue(self._count("zzalpha").exists())

    def test_import_is_the_complete_list(self):
        import_terms("zzalpha\nzzbeta")

        self.assertEqual(ReservedUsername.objects.count(), 2)

    def test_importing_empty_text_clears_the_list(self):
        ReservedUsername.objects.create(pattern="zzdropme")

        count = import_terms("")

        self.assertEqual(count, 0)
        self.assertEqual(ReservedUsername.objects.count(), 0)


class ImportExportAdminViewTests(TestCase):
    """The admin copy-and-paste page is wired up end to end."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="zzadmin", email="zzadmin@example.com", password="pw"
        )
        self.client.force_login(self.admin)
        self.url = reverse(
            "admin:cilogon_reservedusername_import_export"
        )

    def test_get_shows_active_terms_for_export(self):
        ReservedUsername.objects.create(pattern="zzexportme", active=True)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "zzexportme")

    def test_post_imports_pasted_terms(self):
        response = self.client.post(
            self.url, {"terms": "zzpasted | via admin"}
        )

        self.assertEqual(response.status_code, 302)
        term = ReservedUsername.objects.get(pattern="zzpasted")
        self.assertEqual(term.note, "via admin")
        self.assertTrue(term.active)

    def test_post_replaces_the_whole_list(self):
        ReservedUsername.objects.create(pattern="zzoldterm")

        self.client.post(self.url, {"terms": "zznewterm"})

        self.assertFalse(
            ReservedUsername.objects.filter(pattern="zzoldterm").exists()
        )
        self.assertTrue(
            ReservedUsername.objects.filter(pattern="zznewterm").exists()
        )


class RegisterViewInlineWarningTests(TestCase):
    """
    A reserved username is called out inline, above the field, as well as in
    the existing pop-up notification.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _post(self, data):
        request = self.factory.post("/register/", data=data)
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        request.user = MagicMock()
        request.user.is_authenticated = False
        return request

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
        return_value=(True, {"sub": "test-sub-123", "email": "t@example.com"}),
    )
    def test_reserved_username_shows_inline_warning(self, mock_userinfo):
        ReservedUsername.objects.create(pattern="zzreserved", active=True)

        request = self._post(
            {
                "username": "zzreserved99",
                "full_name": "New User",
                "email": "new@example.com",
                "accept_terms": "on",
            }
        )
        response = register(request)

        self.assertIn(INLINE_WARNING_MARKER, response.content)

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
        return_value=(True, {"sub": "test-sub-123", "email": "t@example.com"}),
    )
    def test_non_reserved_error_has_no_inline_warning(self, mock_userinfo):
        # An allowed username that fails for another reason (missing terms)
        # re-renders the form without the reserved-username warning.
        request = self._post(
            {
                "username": "martineve",
                "full_name": "New User",
                "email": "new@example.com",
            }
        )
        response = register(request)

        self.assertNotIn(INLINE_WARNING_MARKER, response.content)
