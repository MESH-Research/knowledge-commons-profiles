"""Tests for legacy BuddyPress-style profile URLs.

The following URLs must reach the profile edit page so that bookmarks and
inbound links from the legacy WordPress/BuddyPress front end keep working:

  * /members/<username>/profile/edit/
  * /members/<username>/profile/change-avatar/
  * /members/<username>/profile/change-cover-image/
"""

from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile


class LegacyProfileEditUrlTests(TestCase):
    """The three legacy URLs should land the user on the edit profile page."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            password="pass1234",
        )
        Profile.objects.create(
            username="alice",
            name="Alice",
            title="Researcher",
        )
        self.client = Client()
        self.client.login(username="alice", password="pass1234")

    def _get_edit_page(self, url):
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # The edit profile template uniquely contains these field IDs.
        self.assertIn('name="name"', content)
        self.assertIn('id="mastodon_edit"', content)
        return content

    def test_profile_edit_url_serves_edit_page(self):
        content = self._get_edit_page("/members/alice/profile/edit/")
        # The plain edit URL must not auto-open either modal.
        self.assertNotIn('id="auto-open-modal"', content)

    def test_change_avatar_url_opens_avatar_modal(self):
        content = self._get_edit_page(
            "/members/alice/profile/change-avatar/"
        )
        self.assertIn('id="auto-open-modal"', content)
        self.assertIn('data-modal-target="avatarModal"', content)

    def test_change_cover_image_url_opens_cover_modal(self):
        content = self._get_edit_page(
            "/members/alice/profile/change-cover-image/"
        )
        self.assertIn('id="auto-open-modal"', content)
        self.assertIn('data-modal-target="coverModal"', content)


class LegacyProfileEditUrlPermissionTests(TestCase):
    """Non-staff users may not use the legacy URLs to edit someone else."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice",
            password="pass1234",
        )
        Profile.objects.create(
            username="alice",
            name="Alice",
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="pass1234",
        )
        Profile.objects.create(
            username="bob",
            name="Bob",
        )
        self.client = Client()
        self.client.login(username="bob", password="pass1234")

    def test_non_staff_cannot_use_profile_edit_for_other_user(self):
        response = self.client.get("/members/alice/profile/edit/")
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_use_change_avatar_for_other_user(self):
        response = self.client.get("/members/alice/profile/change-avatar/")
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_use_change_cover_image_for_other_user(self):
        response = self.client.get(
            "/members/alice/profile/change-cover-image/"
        )
        self.assertEqual(response.status_code, 403)
