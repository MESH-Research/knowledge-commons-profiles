
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.http import QueryDict
from django.template import Context
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.newprofile.forms import (
    AcademicInterestsSelect2TagWidget,
)
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.forms import SanitizedTinyMCE
from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile


class SanitizedTinyMCETests(TestCase):
    def setUp(self):
        self.widget = SanitizedTinyMCE()

    def test_init_creates_widget(self):
        """Test that the widget initializes correctly"""
        self.assertIsNotNone(self.widget)

    def test_allowed_tags(self):
        """Allowlist matches the editor toolbar (issue #540): bold,
        italic, links, anchors, lists, plus the structural p/br."""
        allowed_tags = [
            "p",
            "br",
            "b",
            "i",
            "em",
            "strong",
            "a",
            "ul",
            "ol",
            "li",
        ]
        for tag in allowed_tags:
            html = f"<{tag}>Test</{tag}>"
            result = self.widget.value_from_datadict(
                {"content": html}, {}, "content"
            )
            self.assertIn(f"<{tag}>", result)

    def test_disallowed_tags_removed(self):
        """Anything outside the toolbar allowlist is stripped (issue #540)."""
        disallowed_tags = [
            "script",
            "iframe",
            "object",
            "embed",
            "u",
            "h1",
            "h2",
            "h3",
            "table",
            "img",
            "font",
            "div",
            "span",
        ]
        for tag in disallowed_tags:
            html = f"<{tag}>Test</{tag}>"
            result = self.widget.value_from_datadict(
                {"content": html}, {}, "content"
            )
            self.assertNotIn(f"<{tag}>", result)

    def test_allowed_attributes(self):
        """href/title (links) and id/name (anchors) are preserved."""
        html = '<a href="https://example.com" title="Example">Link</a>'
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('href="https://example.com"', result)
        self.assertIn('title="Example"', result)

        html = '<a id="bookmark">Anchor</a>'
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('id="bookmark"', result)

    def test_disallowed_attributes_removed(self):
        """Test that disallowed attributes are removed"""
        html = (
            '<a href="https://example.com" onclick="alert(\'XSS\')">Link</a>'
        )
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('href="https://example.com"', result)
        self.assertNotIn('onclick="alert', result)

    def test_linkify(self):
        """Test that URLs are converted to links"""
        html = "<p>Visit https://example.com for more information</p>"
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('<a href="https://example.com"', result)

    def test_empty_value(self):
        """Test empty value handling"""
        result = self.widget.value_from_datadict(
            {"content": ""}, {}, "content"
        )
        self.assertEqual(result, "")

        result = self.widget.value_from_datadict({}, {}, "content")
        self.assertIsNone(result)


class AcademicInterestsSelect2TagWidgetTests(TestCase):
    """Tests for issue #522: free-text additions must be turned into
    AcademicInterest rows so the form posts integer PKs, not raw text."""

    def setUp(self):
        self.interest1 = AcademicInterest.objects.create(text="Python")
        self.interest2 = AcademicInterest.objects.create(text="Django")
        self.widget = AcademicInterestsSelect2TagWidget()

    def _datadict(self, values):
        qd = QueryDict(mutable=True)
        qd.setlist("academic_interests", values)
        return qd

    def test_queryset(self):
        """Widget keeps the AcademicInterest queryset on the class."""
        queryset = self.widget.queryset
        self.assertEqual(queryset.model, AcademicInterest)

    def test_value_from_datadict_creates_new_interest_for_unknown_text(self):
        """A typed-in tag that does not match any PK is created and its PK
        comes back in the cleaned list (regression for #522)."""
        before = AcademicInterest.objects.count()

        result = self.widget.value_from_datadict(
            self._datadict(["pig latin"]), {}, "academic_interests"
        )

        new_interest = AcademicInterest.objects.get(text="pig latin")
        self.assertEqual(AcademicInterest.objects.count(), before + 1)
        self.assertEqual(result, [str(new_interest.pk)])

    def test_value_from_datadict_returns_pks_for_existing_pk_inputs(self):
        """When the form posts existing PKs, the widget passes them through
        as strings without creating new rows."""
        before = AcademicInterest.objects.count()

        result = self.widget.value_from_datadict(
            self._datadict([str(self.interest1.pk), str(self.interest2.pk)]),
            {},
            "academic_interests",
        )

        self.assertEqual(AcademicInterest.objects.count(), before)
        self.assertEqual(
            sorted(result),
            sorted([str(self.interest1.pk), str(self.interest2.pk)]),
        )

    def test_value_from_datadict_handles_mixed_existing_and_new(self):
        """Mix of existing PK and new free text: only the free-text row is
        created; both come back as PK strings."""
        before = AcademicInterest.objects.count()

        result = self.widget.value_from_datadict(
            self._datadict([str(self.interest1.pk), "pig latin"]),
            {},
            "academic_interests",
        )

        self.assertEqual(AcademicInterest.objects.count(), before + 1)
        new_interest = AcademicInterest.objects.get(text="pig latin")
        self.assertIn(str(self.interest1.pk), result)
        self.assertIn(str(new_interest.pk), result)
        self.assertEqual(len(result), 2)

    def test_value_from_datadict_dedupes_text_matching_existing_row(self):
        """If the typed text exactly matches an existing row's text, reuse
        that row instead of creating a duplicate."""
        before = AcademicInterest.objects.count()

        result = self.widget.value_from_datadict(
            self._datadict(["Python"]), {}, "academic_interests"
        )

        self.assertEqual(AcademicInterest.objects.count(), before)
        self.assertEqual(result, [str(self.interest1.pk)])

    def test_value_from_datadict_strips_whitespace_and_skips_empty(self):
        """Empty / whitespace-only entries are dropped; surrounding
        whitespace is stripped before matching/creating."""
        before = AcademicInterest.objects.count()

        result = self.widget.value_from_datadict(
            self._datadict(["  ", "", "  pig latin  "]),
            {},
            "academic_interests",
        )

        self.assertEqual(AcademicInterest.objects.count(), before + 1)
        new_interest = AcademicInterest.objects.get(text="pig latin")
        self.assertEqual(result, [str(new_interest.pk)])

    def test_profile_form_widget_creates_new_interest_on_submit(self):
        """End-to-end via ProfileForm: the widget bound to the form's
        academic_interests field also performs the conversion."""
        profile = Profile.objects.create(
            username="form_test_user", name="Form Test"
        )
        form = ProfileForm(instance=profile)
        widget = form.fields["academic_interests"].widget

        before = AcademicInterest.objects.count()
        result = widget.value_from_datadict(
            self._datadict([str(self.interest1.pk), "pig latin"]),
            {},
            "academic_interests",
        )

        self.assertEqual(AcademicInterest.objects.count(), before + 1)
        new_interest = AcademicInterest.objects.get(text="pig latin")
        self.assertIn(str(self.interest1.pk), result)
        self.assertIn(str(new_interest.pk), result)


class EditProfileViewAcademicInterestsTests(TestCase):
    """Regression test for #522 against the live edit_profile view path."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        self.profile = Profile.objects.create(
            username="alice", name="Alice"
        )
        self.existing = AcademicInterest.objects.create(text="Python")
        self.profile.academic_interests.add(self.existing)
        self.client.login(username="alice", password="pass1234")
        self.url = reverse("edit_profile")

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile."
        "index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile."
        "send_webhook_user_update"
    )
    def test_post_with_invalid_other_field_still_renders_without_500(
        self, mock_webhook, mock_index
    ):
        """If validation fails on some other field while a new interest was
        typed in, the re-render of the form must not crash trying to resolve
        the typed-in text against the AcademicInterest queryset (#522)."""
        del mock_webhook, mock_index

        resp = self.client.post(
            self.url,
            {
                "academic_interests": [str(self.existing.pk), "pig latin"],
                "reference_style": "MHRA",
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            AcademicInterest.objects.filter(text="pig latin").exists()
        )

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile."
        "index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile."
        "send_webhook_user_update"
    )
    def test_post_with_new_free_text_interest_persists_through_view(
        self, mock_webhook, mock_index
    ):
        del mock_webhook, mock_index
        """A POST that includes a brand-new typed interest succeeds and the
        new AcademicInterest is attached to the profile (#522)."""
        new_text = "pig latin"
        self.assertFalse(
            AcademicInterest.objects.filter(text=new_text).exists()
        )

        resp = self.client.post(
            self.url,
            {
                "name": "Alice",
                "title": "Researcher",
                "academic_interests": [str(self.existing.pk), new_text],
                "reference_style": "MHRA",
            },
        )

        self.assertEqual(resp.status_code, 302)
        new_interest = AcademicInterest.objects.get(text=new_text)
        attached = set(
            self.profile.academic_interests.values_list("pk", flat=True)
        )
        self.assertIn(self.existing.pk, attached)
        self.assertIn(new_interest.pk, attached)


class ProfileFormTests(TestCase):
    def setUp(self):
        # Create a profile with some data
        self.profile = Profile.objects.create(
            username="testuser",
            name="Test User",
            about_user="About me\nNew line",
            education="Education\nNew line",
            upcoming_talks="Talks\nNew line",
            projects="Projects\nNew line",
            publications="Publications\nNew line",
        )

        # Create some academic interests
        self.interest1 = AcademicInterest.objects.create(text="Python")
        self.interest2 = AcademicInterest.objects.create(text="Django")

        # Add interests to profile
        self.profile.academic_interests.add(self.interest1, self.interest2)

    def test_init_without_instance(self):
        """Test initialization without an instance"""
        form = ProfileForm()
        # Should not raise any exceptions when no instance is provided
        self.assertIsInstance(form, ProfileForm)

    def test_meta_fields(self):
        """Test that all required fields are included in the form"""
        form = ProfileForm()

        # Check a sample of important fields
        self.assertIn("name", form.fields)
        self.assertIn("title", form.fields)
        self.assertIn("academic_interests", form.fields)
        self.assertIn("about_user", form.fields)
        self.assertIn("education", form.fields)
        self.assertIn("show_works", form.fields)
        self.assertIn("show_cv", form.fields)

    def test_widget_classes(self):
        """Test that widgets are correctly assigned"""
        form = ProfileForm()

        # Check widget types for some fields
        self.assertEqual(
            form.fields["academic_interests"].widget.__class__,
            AcademicInterestsSelect2TagWidget,
        )
        self.assertEqual(
            form.fields["projects"].widget.__class__, SanitizedTinyMCE
        )
        self.assertEqual(
            form.fields["publications"].widget.__class__, SanitizedTinyMCE
        )


class BrTagInjectionTests(TestCase):
    """Tests for issue #374: <br> tags inserted around list items."""

    LIST_HTML = (
        "<ul>\n<li>Item one</li>\n<li>Item two</li>\n</ul>"
    )
    ORDERED_LIST_HTML = (
        "<ol>\n<li>First</li>\n<li>Second</li>\n</ol>"
    )
    MIXED_HTML = (
        '<p>Hello <strong>world</strong></p>\n'
        "<ul>\n<li>Item</li>\n</ul>\n"
        '<p>Visit <a href="https://example.com">here</a></p>'
    )
    NESTED_LIST_HTML = (
        "<ul>\n<li>Parent\n<ul>\n<li>Child</li>\n</ul>\n</li>\n</ul>"
    )

    def _render_about_user(self, about_user_html):
        """Render the about_user block from profile_info.html template."""
        from pathlib import Path
        template_path = Path(
            "knowledge_commons_profiles/templates/newprofile/"
            "partials/profile_info.html"
        )
        template_content = template_path.read_text()

        # Extract the about_user block (lines 4-8 of the template)
        lines = template_content.split("\n")
        about_block_lines = []
        capture = False
        for line in lines:
            if "about_user" in line and "{% if" in line:
                capture = True
            if capture:
                about_block_lines.append(line)
            if capture and "{% endif %}" in line:
                break

        about_block = "\n".join(about_block_lines)
        # Remove {% load static %} since we don't need it for this block
        about_block = about_block.replace("{% load static %}", "")

        from django.template import Template as DjangoTemplate
        template = DjangoTemplate(about_block)
        context = Context({"about_user": about_user_html})
        return template.render(context)

    # --- Bug reproduction tests (should FAIL before fix) ---

    def test_template_rendering_does_not_add_br_to_lists(self):
        """Rendered template should not insert <br> adjacent to <li> tags."""
        rendered = self._render_about_user(self.LIST_HTML)
        self.assertNotRegex(
            rendered,
            r"<br>\s*<li>",
            "Found <br> before <li> in rendered output",
        )
        self.assertNotRegex(
            rendered,
            r"</li>\s*<br>",
            "Found <br> after </li> in rendered output",
        )

    def test_template_rendering_preserves_ordered_lists_without_br(self):
        """Rendered template should not insert <br> in <ol> lists."""
        rendered = self._render_about_user(self.ORDERED_LIST_HTML)
        self.assertNotRegex(
            rendered,
            r"<br>\s*<li>",
            "Found <br> before <li> in rendered output",
        )
        self.assertNotRegex(
            rendered,
            r"</li>\s*<br>",
            "Found <br> after </li> in rendered output",
        )

    def test_tinymce_forced_root_block_is_paragraph(self):
        """TinyMCE forced_root_block should be 'p', not empty."""
        self.assertEqual(
            settings.TINYMCE_DEFAULT_CONFIG["forced_root_block"],
            "p",
            "forced_root_block should be 'p' to produce proper paragraphs",
        )

    # --- Regression guard tests (should PASS before and after fix) ---

    def test_list_html_preserved_without_spurious_br(self):
        """Lists round-trip through sanitisation without #374's <br>
        injection around <li>."""
        widget = SanitizedTinyMCE()
        result = widget.value_from_datadict(
            {"content": self.LIST_HTML}, {}, "content"
        )
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)
        self.assertNotRegex(
            result,
            r"<br>\s*<li>",
            "Sanitization added <br> before <li>",
        )

    def test_mixed_html_content_round_trip(self):
        """Bold, links, and lists all survive sanitisation."""
        widget = SanitizedTinyMCE()
        result = widget.value_from_datadict(
            {"content": self.MIXED_HTML}, {}, "content"
        )
        self.assertIn("<strong>", result)
        self.assertIn("<a ", result)
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)

    def test_content_loaded_into_form_preserves_html(self):
        """Form initial values aren't sanitised on load — only on save —
        so stored content round-trips into the edit form unchanged."""
        profile = Profile.objects.create(
            username="htmltestuser",
            name="HTML Test",
            about_user=self.LIST_HTML,
            education=self.ORDERED_LIST_HTML,
        )
        form = ProfileForm(instance=profile)
        self.assertEqual(form.initial["about_user"], self.LIST_HTML)
        self.assertEqual(form.initial["education"], self.ORDERED_LIST_HTML)

    def test_nested_list_html_preserved(self):
        """Nested lists survive sanitisation without <br> injection."""
        widget = SanitizedTinyMCE()
        result = widget.value_from_datadict(
            {"content": self.NESTED_LIST_HTML}, {}, "content"
        )
        self.assertIn("<ul>", result)
        self.assertNotRegex(
            result,
            r"<br>\s*<li>",
            "Sanitization added <br> before <li> in nested list",
        )
