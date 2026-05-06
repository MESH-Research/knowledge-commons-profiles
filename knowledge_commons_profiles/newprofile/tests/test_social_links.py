"""Tests for issue #544: restoring Facebook / LinkedIn / Website
inputs and display on the profile, with legacy-friendly coercion of
bare usernames and scheme-less URLs into fully-qualified URLs."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.newprofile.forms import CoercedURLField
from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile


class CoercedURLFieldTests(TestCase):
    """Field-level tests for the URL field used by facebook / linkedin /
    website on ProfileForm."""

    def test_full_url_passes_through(self):
        field = CoercedURLField(
            required=False,
            platform_url_prefix="https://facebook.com/",
        )
        self.assertEqual(
            field.clean("https://facebook.com/me"), "https://facebook.com/me"
        )

    def test_bare_token_coerced_to_platform_url(self):
        field = CoercedURLField(
            required=False,
            platform_url_prefix="https://facebook.com/",
        )
        self.assertEqual(field.clean("martineve"), "https://facebook.com/martineve")

    def test_scheme_less_host_coerced(self):
        field = CoercedURLField(required=False)
        self.assertEqual(
            field.clean("example.com/path"), "https://example.com/path"
        )

    def test_bare_token_without_prefix_rejected(self):
        field = CoercedURLField(required=False)
        with self.assertRaises(ValidationError):
            field.clean("notaurl")

    def test_blank_allowed_when_not_required(self):
        field = CoercedURLField(required=False)
        self.assertEqual(field.clean(""), "")

    def test_linkedin_path_coerced_under_host(self):
        field = CoercedURLField(
            required=False,
            platform_url_prefix="https://linkedin.com/in/",
        )
        self.assertEqual(
            field.clean("in/martineve"), "https://linkedin.com/in/martineve"
        )

    def test_invalid_scheme_rejected(self):
        field = CoercedURLField(required=False)
        with self.assertRaises(ValidationError):
            field.clean("ftp://example.com")


class ProfileFormSocialFieldsTests(TestCase):
    """ProfileForm-level tests confirming the three new fields behave
    correctly when bound to a Profile instance."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="socialtest",
            name="Social Test",
            title="Researcher",
        )

    def _bind(self, **extra):
        data = {
            "name": "Social Test",
            "title": "Researcher",
        }
        data.update(extra)
        return ProfileForm(data, instance=self.profile)

    def test_facebook_full_url_round_trips(self):
        form = self._bind(facebook="https://facebook.com/martineve")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["facebook"], "https://facebook.com/martineve"
        )

    def test_facebook_bare_token_coerced(self):
        form = self._bind(facebook="martineve")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["facebook"], "https://facebook.com/martineve"
        )

    def test_linkedin_bare_token_coerced(self):
        form = self._bind(linkedin="martineve")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["linkedin"],
            "https://linkedin.com/in/martineve",
        )

    def test_website_full_url_round_trips(self):
        form = self._bind(website="https://martineve.com")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["website"], "https://martineve.com"
        )

    def test_website_scheme_less_coerced(self):
        form = self._bind(website="martineve.com")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["website"], "https://martineve.com"
        )

    def test_website_bare_token_rejected(self):
        form = self._bind(website="notaurl")
        self.assertFalse(form.is_valid())
        self.assertIn("website", form.errors)

    def test_all_three_blank_allowed(self):
        form = self._bind(facebook="", linkedin="", website="")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["facebook"], "")
        self.assertEqual(form.cleaned_data["linkedin"], "")
        self.assertEqual(form.cleaned_data["website"], "")


class EditProfileViewSocialLinksTests(TestCase):
    """End-to-end through /edit-profile/."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        self.profile = Profile.objects.create(
            username="alice",
            name="Alice",
            title="Researcher",
        )
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
    def test_post_persists_social_links(self, mock_webhook, mock_index):
        del mock_webhook, mock_index

        resp = self.client.post(
            self.url,
            {
                "name": "Alice",
                "title": "Researcher",
                "facebook": "martineve",
                "linkedin": "https://linkedin.com/in/martineve",
                "website": "martineve.com",
                "reference_style": "MHRA",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.facebook, "https://facebook.com/martineve"
        )
        self.assertEqual(
            self.profile.linkedin, "https://linkedin.com/in/martineve"
        )
        self.assertEqual(self.profile.website, "https://martineve.com")

    def test_get_renders_three_social_fields(self):
        """Edit page must include input markup for each new field."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('id="facebook_edit"', content)
        self.assertIn('id="linkedin_edit"', content)
        self.assertIn('id="website_edit"', content)
        self.assertIn('name="facebook"', content)
        self.assertIn('name="linkedin"', content)
        self.assertIn('name="website"', content)


class NormaliseLegacySocialUrlsMigrationTests(TestCase):
    """The data migration must normalise legacy values (bare usernames,
    scheme-less hosts) into fully-qualified URLs across the three
    fields, leave already-good URLs untouched, and not touch values
    that look genuinely malformed."""

    def _run_forward(self):
        import importlib

        from django.apps import apps

        mig = importlib.import_module(
            "knowledge_commons_profiles.newprofile.migrations."
            "0053_normalise_legacy_social_urls",
        )
        mig.normalise_legacy_social_urls(apps, schema_editor=None)

    def test_bare_facebook_username_normalised(self):
        p = Profile.objects.create(
            username="legfb", name="Legacy FB", facebook="martineve"
        )
        self._run_forward()
        p.refresh_from_db()
        self.assertEqual(p.facebook, "https://facebook.com/martineve")

    def test_bare_linkedin_username_normalised(self):
        p = Profile.objects.create(
            username="legli", name="Legacy LI", linkedin="martineve"
        )
        self._run_forward()
        p.refresh_from_db()
        self.assertEqual(p.linkedin, "https://linkedin.com/in/martineve")

    def test_scheme_less_website_normalised(self):
        p = Profile.objects.create(
            username="legweb", name="Legacy Web", website="martineve.com"
        )
        self._run_forward()
        p.refresh_from_db()
        self.assertEqual(p.website, "https://martineve.com")

    def test_full_urls_unchanged(self):
        p = Profile.objects.create(
            username="legok",
            name="Already Good",
            facebook="https://facebook.com/me",
            linkedin="https://linkedin.com/in/me",
            website="https://example.com",
        )
        self._run_forward()
        p.refresh_from_db()
        self.assertEqual(p.facebook, "https://facebook.com/me")
        self.assertEqual(p.linkedin, "https://linkedin.com/in/me")
        self.assertEqual(p.website, "https://example.com")

    def test_blanks_unchanged(self):
        p = Profile.objects.create(
            username="legblank", name="Blank", facebook="", linkedin="",
            website="",
        )
        self._run_forward()
        p.refresh_from_db()
        self.assertEqual(p.facebook, "")
        self.assertEqual(p.linkedin, "")
        self.assertEqual(p.website, "")

    def test_idempotent(self):
        """Running the migration twice produces the same result."""
        Profile.objects.create(
            username="idem", name="Idem", facebook="martineve",
            linkedin="martineve", website="martineve.com",
        )
        self._run_forward()
        self._run_forward()
        p = Profile.objects.get(username="idem")
        self.assertEqual(p.facebook, "https://facebook.com/martineve")
        self.assertEqual(p.linkedin, "https://linkedin.com/in/martineve")
        self.assertEqual(p.website, "https://martineve.com")

    def test_unrecognisable_website_left_alone(self):
        """Migration must not damage rows it can't normalise — a bare
        token in `website` has no host to anchor against, so it stays."""
        Profile.objects.create(
            username="legbad", name="Bad", website="notaurl"
        )
        self._run_forward()
        p = Profile.objects.get(username="legbad")
        self.assertEqual(p.website, "notaurl")


class ProfileInfoApiSocialFieldsTests(TestCase):
    """get_profile_info must surface the three new fields so the
    profile-view template can render them."""

    def test_get_profile_info_includes_facebook_linkedin_website(self):
        from knowledge_commons_profiles.newprofile.api import API

        Profile.objects.create(
            username="apitest",
            name="API Test",
            facebook="https://facebook.com/apitest",
            linkedin="https://linkedin.com/in/apitest",
            website="https://apitest.example",
        )
        api = API(
            request=None,
            user="apitest",
            create=False,
            use_wordpress=False,
        )
        info = api.get_profile_info()

        self.assertEqual(info["facebook"], "https://facebook.com/apitest")
        self.assertEqual(
            info["linkedin"], "https://linkedin.com/in/apitest"
        )
        self.assertEqual(info["website"], "https://apitest.example")
