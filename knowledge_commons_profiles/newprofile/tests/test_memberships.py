"""Tests for the Memberships profile field (#370).

These tests exercise the memberships field integration across the model,
form, settings, templates, utils, and HTMX view layers.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.forms import CheckboxInput
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.forms import SanitizedTinyMCE
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import process_orders
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    profile_info,
)


class MembershipsModelTests(TestCase):
    """Tests for the show_memberships model field."""

    def test_show_memberships_defaults_to_true(self):
        """A new Profile should have show_memberships=True by default."""
        profile = Profile.objects.create(
            username="membertest",
            name="Member Test",
        )
        profile.refresh_from_db()
        self.assertTrue(
            profile.show_memberships,
            "show_memberships should default to True",
        )

    def test_memberships_stores_and_retrieves_html(self):
        """The memberships field should round-trip rich HTML content."""
        html = (
            "<p>Member of <strong>ACM</strong> since 2020</p>"
            "<ul><li>IEEE Fellow</li><li>AMS Member</li></ul>"
        )
        profile = Profile.objects.create(
            username="htmltest",
            name="HTML Test",
            memberships=html,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.memberships, html)


class MembershipsFormTests(TestCase):
    """Tests for memberships field integration in ProfileForm."""

    def test_show_memberships_in_form_fields(self):
        """ProfileForm should include the show_memberships field."""
        form = ProfileForm()
        self.assertIn(
            "show_memberships",
            form.fields,
            "show_memberships should be in form fields",
        )

    def test_show_memberships_widget_is_checkbox(self):
        """The show_memberships widget should be a CheckboxInput."""
        form = ProfileForm()
        widget = form.fields["show_memberships"].widget
        self.assertIsInstance(
            widget,
            CheckboxInput,
            f"Expected CheckboxInput, got {type(widget).__name__}",
        )

    def test_memberships_widget_is_sanitized_tinymce(self):
        """The memberships widget should be SanitizedTinyMCE."""
        form = ProfileForm()
        widget = form.fields["memberships"].widget
        self.assertIsInstance(
            widget,
            SanitizedTinyMCE,
            f"Expected SanitizedTinyMCE, got {type(widget).__name__}",
        )

    def test_memberships_initial_value_set_from_instance(self):
        """Form initial['memberships'] should be populated from instance."""
        profile = Profile.objects.create(
            username="inittest",
            name="Init Test",
            memberships="<p>Test membership</p>",
        )
        form = ProfileForm(instance=profile)
        self.assertEqual(
            form.initial.get("memberships"),
            "<p>Test membership</p>",
            "Form initial should contain the instance's memberships value",
        )


class MembershipsSettingsTests(TestCase):
    """Tests for memberships field in PROFILE_FIELDS_LEFT setting."""

    def test_memberships_in_profile_fields_left(self):
        """'memberships' should be listed in PROFILE_FIELDS_LEFT."""
        self.assertIn(
            "memberships",
            settings.PROFILE_FIELDS_LEFT,
            "memberships should be in PROFILE_FIELDS_LEFT",
        )

    def test_memberships_after_projects_in_left_order(self):
        """'memberships' should appear immediately after 'projects'."""
        fields = settings.PROFILE_FIELDS_LEFT
        projects_idx = fields.index("projects")
        memberships_idx = fields.index("memberships")
        self.assertEqual(
            memberships_idx,
            projects_idx + 1,
            f"memberships (index {memberships_idx}) should be right after "
            f"projects (index {projects_idx})",
        )


class MembershipsTemplateTests(TestCase):
    """Tests for memberships display and edit template fragments."""

    def test_display_fragment_renders_when_visible(self):
        """memberships.html should render a div with id='memberships'
        when show_memberships is True."""
        profile = Profile.objects.create(
            username="vistest",
            name="Vis Test",
            show_memberships=True,
        )
        rendered = render_to_string(
            "newprofile/fragments/memberships.html",
            {"profile": profile},
        )
        self.assertIn(
            'id="memberships"',
            rendered,
            "Display fragment should contain memberships div when visible",
        )

    def test_display_fragment_hidden_when_not_visible(self):
        """memberships.html should NOT render a div with id='memberships'
        when show_memberships is False."""
        profile = Profile.objects.create(
            username="hidtest",
            name="Hid Test",
            show_memberships=False,
        )
        rendered = render_to_string(
            "newprofile/fragments/memberships.html",
            {"profile": profile},
        )
        self.assertNotIn(
            'id="memberships"',
            rendered,
            "Display fragment should not contain memberships div when hidden",
        )

    def test_edit_fragment_has_sortable_class(self):
        """memberships_edit.html should include the sortable-item class."""
        profile = Profile.objects.create(
            username="sorttest",
            name="Sort Test",
        )
        form = ProfileForm(instance=profile)
        rendered = render_to_string(
            "newprofile/fragments/memberships_edit.html",
            {"form": form},
        )
        self.assertIn(
            "sortable-item",
            rendered,
            "Edit fragment should include sortable-item class",
        )

    def test_edit_fragment_has_tinymce(self):
        """memberships_edit.html should render a TinyMCE textarea."""
        profile = Profile.objects.create(
            username="tmcetest",
            name="TMCE Test",
        )
        form = ProfileForm(instance=profile)
        rendered = render_to_string(
            "newprofile/fragments/memberships_edit.html",
            {"form": form},
        )
        self.assertIn(
            "tinymce",
            rendered.lower(),
            "Edit fragment should contain a TinyMCE textarea",
        )


class MembershipsUtilsTests(TestCase):
    """Tests for memberships in process_orders utility."""

    def test_process_orders_includes_memberships(self):
        """process_orders should include 'memberships' in the left order
        when it is not explicitly provided (appended from settings)."""
        left_order, _ = process_orders([], [])
        self.assertIn(
            "memberships",
            left_order,
            "process_orders should include memberships in left order",
        )


class MembershipsHTMXViewTests(TestCase):
    """Tests for show_memberships in the profile_info HTMX view context."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="htmxuser", password="testpass"
        )
        self.mock_profile = MagicMock()
        self.mock_profile.show_memberships = True
        self.mock_profile.show_education = True
        self.mock_profile.show_publications = True
        self.mock_profile.show_projects = True
        self.mock_profile.show_academic_interests = True
        self.mock_profile.get_external_memberships.return_value = {}

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    def test_profile_info_context_includes_show_memberships(self, mock_api):
        """The profile_info view should include show_memberships in its
        template context."""
        api_instance = MagicMock()
        api_instance.profile = self.mock_profile
        api_instance.get_profile_info.return_value = self.mock_profile
        api_instance.get_academic_interests.return_value = []
        api_instance.get_education.return_value = ""
        api_instance.get_about_user.return_value = ""
        mock_api.return_value = api_instance

        request = self.factory.get("/htmx/profile-info/htmxuser/")
        request.user = self.user

        response = profile_info(request, "htmxuser")

        self.assertEqual(response.status_code, 200)
        # The view should pass show_memberships to the template.
        # We verify by checking the rendered content contains
        # the memberships OOB swap div (either visible or hidden).
        content = response.content.decode()
        self.assertIn(
            "memberships",
            content,
            "profile_info response should reference the memberships element",
        )
