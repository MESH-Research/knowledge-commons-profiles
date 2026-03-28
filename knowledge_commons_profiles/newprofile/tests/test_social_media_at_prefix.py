"""Tests for the @ prefix on social media handle fields (#392).

These tests verify that the edit profile form displays an @ symbol
before the Mastodon, Twitter/X, and Bluesky input fields to indicate
users do not need to enter the @ symbol themselves, and that leading
@ symbols are stripped from user input on save.
"""

from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Profile


class SocialMediaAtPrefixTests(TestCase):
    """Tests for @ prefix display on social media edit fields."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        Profile.objects.get_or_create(
            username="testuser",
            defaults={"name": "Test User"},
        )
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")

    def test_mastodon_field_has_at_prefix(self):
        """The Mastodon edit field should display an @ prefix."""
        response = self.client.get(reverse("edit_profile"))
        content = response.content.decode()
        self.assertIn(
            'class="at-prefix"',
            content,
            "Mastodon field should have an @ prefix element",
        )
        # Check that @ prefix appears within the mastodon edit span
        mastodon_section = content.split('id="mastodon_edit"')[1].split(
            "</span>"
        )[0]
        self.assertIn(
            "@",
            mastodon_section,
            "Mastodon edit section should contain @ prefix",
        )

    def test_twitter_field_has_at_prefix(self):
        """The Twitter/X edit field should display an @ prefix."""
        response = self.client.get(reverse("edit_profile"))
        content = response.content.decode()
        twitter_section = content.split('id="twitter_edit"')[1].split(
            "</span>"
        )[0]
        self.assertIn(
            "@",
            twitter_section,
            "Twitter edit section should contain @ prefix",
        )

    def test_bluesky_field_has_at_prefix(self):
        """The Bluesky edit field should display an @ prefix."""
        response = self.client.get(reverse("edit_profile"))
        content = response.content.decode()
        bluesky_section = content.split('id="bluesky_edit"')[1].split(
            "</span>"
        )[0]
        self.assertIn(
            "@",
            bluesky_section,
            "Bluesky edit section should contain @ prefix",
        )

    def test_orcid_field_does_not_have_at_prefix(self):
        """The ORCID field should NOT have an @ prefix."""
        response = self.client.get(reverse("edit_profile"))
        content = response.content.decode()
        orcid_section = content.split('id="orcid_edit"')[1].split(
            "</span>"
        )[0]
        self.assertNotIn(
            'class="at-prefix"',
            orcid_section,
            "ORCID edit section should not contain an @ prefix",
        )


class SocialMediaAtStrippingTests(TestCase):
    """Tests that leading @ symbols are stripped from social media handles."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="striptest",
            name="Strip Test",
        )

    def test_twitter_leading_at_is_stripped(self):
        """Leading @ should be stripped from Twitter handle."""
        form = ProfileForm(
            data={"twitter": "@myhandle", "name": "Strip Test"},
            instance=self.profile,
        )
        form.is_valid()
        self.assertEqual(form.cleaned_data["twitter"], "myhandle")

    def test_twitter_without_at_is_unchanged(self):
        """Twitter handle without @ should be left as-is."""
        form = ProfileForm(
            data={"twitter": "myhandle", "name": "Strip Test"},
            instance=self.profile,
        )
        form.is_valid()
        self.assertEqual(form.cleaned_data["twitter"], "myhandle")

    def test_bluesky_leading_at_is_stripped(self):
        """Leading @ should be stripped from Bluesky handle."""
        form = ProfileForm(
            data={"bluesky": "@user.bsky.social", "name": "Strip Test"},
            instance=self.profile,
        )
        form.is_valid()
        self.assertEqual(form.cleaned_data["bluesky"], "user.bsky.social")

    def test_mastodon_leading_at_is_stripped(self):
        """Leading @ should be stripped from Mastodon handle."""
        form = ProfileForm(
            data={
                "mastodon": "@user@mastodon.social",
                "name": "Strip Test",
            },
            instance=self.profile,
        )
        form.is_valid()
        self.assertEqual(
            form.cleaned_data["mastodon"], "user@mastodon.social"
        )

    def test_mastodon_without_leading_at_is_unchanged(self):
        """Mastodon handle without leading @ should be left as-is."""
        form = ProfileForm(
            data={
                "mastodon": "user@mastodon.social",
                "name": "Strip Test",
            },
            instance=self.profile,
        )
        form.is_valid()
        self.assertEqual(
            form.cleaned_data["mastodon"], "user@mastodon.social"
        )
