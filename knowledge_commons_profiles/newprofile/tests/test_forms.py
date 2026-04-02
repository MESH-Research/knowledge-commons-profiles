from unittest.mock import patch

from django.conf import settings
from django.template import Context
from django.test import TestCase

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
        """Test that allowed tags are preserved"""
        allowed_tags = [
            "p",
            "b",
            "i",
            "u",
            "em",
            "strong",
            "a",
            "ul",
            "ol",
            "li",
            "br",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "table",
            "img",
        ]
        for tag in allowed_tags:
            html = f"<{tag}>Test</{tag}>"
            result = self.widget.value_from_datadict(
                {"content": html}, {}, "content"
            )
            self.assertIn(f"<{tag}>", result)

    def test_disallowed_tags_removed(self):
        """Test that disallowed tags are removed"""
        disallowed_tags = ["script", "iframe", "object", "embed"]
        for tag in disallowed_tags:
            html = f"<{tag}>Test</{tag}>"
            result = self.widget.value_from_datadict(
                {"content": html}, {}, "content"
            )
            self.assertNotIn(f"<{tag}>", result)

    def test_allowed_attributes(self):
        """Test that allowed attributes are preserved"""
        html = '<a href="https://example.com" title="Example">Link</a>'
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('href="https://example.com"', result)
        self.assertIn('title="Example"', result)

        html = '<img src="image.jpg" alt="Image" width="100" height="100">'
        result = self.widget.value_from_datadict(
            {"content": html}, {}, "content"
        )
        self.assertIn('src="image.jpg"', result)
        self.assertIn('alt="Image"', result)
        self.assertIn('width="100"', result)
        self.assertIn('height="100"', result)

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
    def setUp(self):
        # Create some academic interests
        self.interest1 = AcademicInterest.objects.create(text="Python")
        self.interest2 = AcademicInterest.objects.create(text="Django")
        self.widget = AcademicInterestsSelect2TagWidget()

    def test_queryset(self):
        """Test that the widget has the correct queryset"""
        queryset = self.widget.queryset
        self.assertEqual(queryset.model, AcademicInterest)

    @patch(
        "knowledge_commons_profiles.newprofile.forms."
        "ModelSelect2TagWidget.value_from_datadict"
    )
    def test_existing_values(self, mock_parent_method):
        """Test handling of existing values"""
        mock_parent_method.return_value = ["Python", "Django"]

        result = self.widget.value_from_datadict({}, {}, "academic_interests")

        # Should return PKs of existing interests
        self.assertIn("Python", result)
        self.assertIn("Django", result)


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
        """Sanitization should not add <br> to clean list HTML."""
        widget = SanitizedTinyMCE()
        result = widget.value_from_datadict(
            {"content": self.LIST_HTML}, {}, "content"
        )
        self.assertNotRegex(
            result,
            r"<br>\s*<li>",
            "Sanitization added <br> before <li>",
        )

    def test_mixed_html_content_round_trip(self):
        """Mixed content survives sanitization with structure intact."""
        widget = SanitizedTinyMCE()
        result = widget.value_from_datadict(
            {"content": self.MIXED_HTML}, {}, "content"
        )
        self.assertIn("<ul>", result)
        self.assertIn("<li>", result)
        self.assertIn("<strong>", result)
        self.assertIn("<a ", result)

    def test_content_loaded_into_form_preserves_html(self):
        """Form initial values should preserve stored HTML unchanged."""
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
        """Nested lists survive sanitization without <br> injection."""
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
