"""
Tests for the common profiles_email helpers.
"""

from django.test import SimpleTestCase

from knowledge_commons_profiles.common.profiles_email import normalize_email


class NormalizeEmailTests(SimpleTestCase):
    def test_lowercases_mixed_case_email(self):
        self.assertEqual(
            normalize_email("Foo@Bar.com"),
            "foo@bar.com",
        )

    def test_lowercases_uppercase_email(self):
        self.assertEqual(
            normalize_email("USER@EXAMPLE.COM"),
            "user@example.com",
        )

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(
            normalize_email("  USER@example.com  "),
            "user@example.com",
        )

    def test_already_lowercase_unchanged(self):
        self.assertEqual(
            normalize_email("user@example.com"),
            "user@example.com",
        )

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_email(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(normalize_email(None))

    def test_unicode_is_lowercased(self):
        # Capital U with umlaut lowercases to its lowercase form.
        self.assertEqual(
            normalize_email("Ü@example.com"),
            "ü@example.com",
        )
