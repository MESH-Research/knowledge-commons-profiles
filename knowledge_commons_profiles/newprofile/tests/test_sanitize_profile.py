"""
Tests for the sanitize_profile management command.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile


class SanitizeProfileCommandTests(TestCase):
    """Tests for the sanitize_profile management command."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="testuser",
            about_user=(
                "&lt;span&gt;Some bio text.&lt;/span&gt;"
                " <em>A Book Title</em>"
            ),
            education="&lt;div&gt;PhD&lt;/div&gt; in Literature",
            publications="<p>Clean publication</p>",
            projects=None,
        )

    def test_sanitizes_all_html_fields_by_default(self):
        """Without --field, all HTML fields should be sanitized."""
        out = StringIO()
        call_command("sanitize_profile", "testuser", stdout=out)

        self.profile.refresh_from_db()
        self.assertNotIn("&lt;span&gt;", self.profile.about_user)
        self.assertNotIn("<span>", self.profile.about_user)
        self.assertIn("Some bio text.", self.profile.about_user)
        self.assertIn("<em>A Book Title</em>", self.profile.about_user)

        self.assertNotIn("&lt;div&gt;", self.profile.education)
        self.assertIn("PhD", self.profile.education)

    def test_sanitizes_single_field(self):
        """With --field, only that field should be sanitized."""
        out = StringIO()
        call_command(
            "sanitize_profile", "testuser",
            field="about_user", stdout=out,
        )

        self.profile.refresh_from_db()
        self.assertNotIn("&lt;span&gt;", self.profile.about_user)
        self.assertIn("Some bio text.", self.profile.about_user)

        # education should be untouched
        self.assertIn("&lt;div&gt;", self.profile.education)

    def test_handles_none_fields(self):
        """Fields with None values should be skipped without error."""
        out = StringIO()
        call_command(
            "sanitize_profile", "testuser",
            field="projects", stdout=out,
        )
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.projects)

    def test_invalid_field_name(self):
        """An invalid field name should produce an error."""
        err = StringIO()
        call_command(
            "sanitize_profile", "testuser",
            field="nonexistent", stderr=err,
        )
        self.assertIn("not a valid", err.getvalue())

    def test_nonexistent_profile(self):
        """A nonexistent username should produce an error."""
        err = StringIO()
        call_command("sanitize_profile", "nobody", stderr=err)
        self.assertIn("not found", err.getvalue())

    def test_dry_run(self):
        """With --dry-run, no changes should be saved."""
        out = StringIO()
        call_command(
            "sanitize_profile", "testuser",
            dry_run=True, stdout=out,
        )

        self.profile.refresh_from_db()
        # Should still have the escaped entities
        self.assertIn("&lt;span&gt;", self.profile.about_user)
        self.assertIn("Would update", out.getvalue())

    def test_shows_before_after(self):
        """Output should show what changed."""
        out = StringIO()
        call_command("sanitize_profile", "testuser", stdout=out)
        output = out.getvalue()
        self.assertIn("about_user", output)
