"""Tests for the Works chart visibility toggle (#452).

These tests verify that the show_works_chart field controls whether
the Vega chart is displayed in the Works section.
"""


from django.forms import CheckboxInput
from django.template.loader import render_to_string
from django.test import TestCase

from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile


class ShowWorksChartModelTests(TestCase):
    """Tests for the show_works_chart model field."""

    def test_show_works_chart_defaults_to_true(self):
        """A new Profile should have show_works_chart=True by default."""
        profile = Profile.objects.create(
            username="charttest",
            name="Chart Test",
        )
        profile.refresh_from_db()
        self.assertTrue(
            profile.show_works_chart,
            "show_works_chart should default to True",
        )

    def test_show_works_chart_can_be_set_false(self):
        """show_works_chart should be settable to False."""
        profile = Profile.objects.create(
            username="chartoff",
            name="Chart Off",
            show_works_chart=False,
        )
        profile.refresh_from_db()
        self.assertFalse(profile.show_works_chart)


class ShowWorksChartFormTests(TestCase):
    """Tests for show_works_chart in ProfileForm."""

    def test_show_works_chart_in_form_fields(self):
        """ProfileForm should include the show_works_chart field."""
        form = ProfileForm()
        self.assertIn(
            "show_works_chart",
            form.fields,
            "show_works_chart should be in form fields",
        )

    def test_show_works_chart_widget_is_checkbox(self):
        """The show_works_chart widget should be a CheckboxInput."""
        form = ProfileForm()
        widget = form.fields["show_works_chart"].widget
        self.assertIsInstance(
            widget,
            CheckboxInput,
            f"Expected CheckboxInput, got {type(widget).__name__}",
        )


class ShowWorksChartEditTemplateTests(TestCase):
    """Tests for show_works_chart in the works edit template."""

    def test_works_edit_contains_show_works_chart(self):
        """works_edit.html should render the show_works_chart checkbox."""
        profile = Profile.objects.create(
            username="edittest",
            name="Edit Test",
        )
        form = ProfileForm(instance=profile)
        rendered = render_to_string(
            "newprofile/fragments/works_edit.html",
            {"form": form},
        )
        self.assertIn(
            "show_works_chart",
            rendered,
            "works_edit.html should contain show_works_chart field",
        )

    def test_works_edit_has_show_chart_label(self):
        """works_edit.html should have a label for the chart toggle."""
        profile = Profile.objects.create(
            username="labeltest",
            name="Label Test",
        )
        form = ProfileForm(instance=profile)
        rendered = render_to_string(
            "newprofile/fragments/works_edit.html",
            {"form": form},
        )
        self.assertIn(
            "Show chart",
            rendered,
            "works_edit.html should contain 'Show chart' label",
        )


class ShowWorksChartDisplayTemplateTests(TestCase):
    """Tests for chart visibility in the works display template."""

    def test_works_display_shows_chart_div_when_enabled(self):
        """works.html should include chart div when show_works_chart
        is True."""
        profile = Profile.objects.create(
            username="chartvis",
            name="Chart Vis",
            show_works=True,
            show_works_chart=True,
        )
        rendered = render_to_string(
            "newprofile/fragments/works.html",
            {"profile": profile, "username": "chartvis"},
        )
        self.assertIn(
            'id="chart"',
            rendered,
            "Chart div should be present when show_works_chart is True",
        )

    def test_works_display_hides_chart_div_when_disabled(self):
        """works.html should NOT include chart div when show_works_chart
        is False."""
        profile = Profile.objects.create(
            username="charthid",
            name="Chart Hid",
            show_works=True,
            show_works_chart=False,
        )
        rendered = render_to_string(
            "newprofile/fragments/works.html",
            {"profile": profile, "username": "charthid"},
        )
        self.assertNotIn(
            'id="chart"',
            rendered,
            "Chart div should not be present when show_works_chart is False",
        )


class ShowWorksChartDepositsPartialTests(TestCase):
    """Tests for chart rendering gated by show_works_chart."""

    def test_deposits_partial_renders_vegaembed_when_chart_enabled(self):
        """works_deposits.html should include vegaEmbed call when
        show_works_chart is True."""
        profile = Profile.objects.create(
            username="vegaon",
            name="Vega On",
            show_works=True,
            show_works_chart=True,
        )
        rendered = render_to_string(
            "newprofile/partials/works_deposits.html",
            {
                "profile": profile,
                "works_html": [{"type": "Book", "works": []}],
                "works_headings_ordered": {},
                "chart": '{"$schema": "test"}',
            },
        )
        self.assertIn(
            "vegaEmbed",
            rendered,
            "vegaEmbed should be called when show_works_chart is True",
        )

    def test_deposits_partial_omits_vegaembed_when_chart_disabled(self):
        """works_deposits.html should NOT include vegaEmbed call when
        show_works_chart is False."""
        profile = Profile.objects.create(
            username="vegaoff",
            name="Vega Off",
            show_works=True,
            show_works_chart=False,
        )
        rendered = render_to_string(
            "newprofile/partials/works_deposits.html",
            {
                "profile": profile,
                "works_html": [{"type": "Book", "works": []}],
                "works_headings_ordered": {},
                "chart": '{"$schema": "test"}',
            },
        )
        self.assertNotIn(
            "vegaEmbed",
            rendered,
            "vegaEmbed should not be called when show_works_chart is False",
        )
