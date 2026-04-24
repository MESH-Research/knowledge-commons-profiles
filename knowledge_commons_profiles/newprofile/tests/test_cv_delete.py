"""Tests for the CV delete AJAX endpoint (issue #523)."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.newprofile.models import Profile


def _make_pdf():
    """Create a minimal valid-looking PDF file for seeding a cv_file."""
    return SimpleUploadedFile(
        "seed.pdf", b"%PDF-1.4 seed", content_type="application/pdf"
    )


class DeleteCvAuthTests(TestCase):
    """Auth / permissions on delete_cv."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        User.objects.create_user(username="bob", password="pass1234")
        User.objects.create_user(
            username="staffmember", password="pass1234", is_staff=True
        )
        Profile.objects.create(username="alice", name="Alice")
        Profile.objects.create(username="bob", name="Bob")

        self.own_url = reverse("delete_cv")
        self.bob_url = reverse(
            "delete_cv_user", kwargs={"username": "bob"}
        )

    def test_anonymous_user_is_redirected(self):
        resp = self.client.post(self.own_url)
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.get(self.own_url)
        self.assertEqual(resp.status_code, 405)

    def test_non_staff_cannot_delete_for_other_user(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.bob_url)
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("Permission denied", data["error"])

    @patch("django.core.files.storage.default_storage")
    def test_staff_can_delete_for_other_user(self, mock_storage):
        mock_storage.save.return_value = "cvs/bob.pdf"
        mock_storage.url.return_value = "/media/cvs/bob.pdf"
        # Seed bob's CV
        profile = Profile.objects.get(username="bob")
        profile.cv_file.save("bob.pdf", _make_pdf(), save=True)

        self.client.login(username="staffmember", password="pass1234")
        resp = self.client.post(self.bob_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])


class DeleteCvBehaviourTests(TestCase):
    """Delete endpoint must clear the model field and remove the file."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(username="alice", name="Alice")
        self.url = reverse("delete_cv")
        self.client.login(username="alice", password="pass1234")

    @patch("django.core.files.storage.default_storage")
    def test_delete_clears_cv_file_on_profile(self, mock_storage):
        mock_storage.save.return_value = "cvs/alice.pdf"
        mock_storage.url.return_value = "/media/cvs/alice.pdf"
        profile = Profile.objects.get(username="alice")
        profile.cv_file.save("alice.pdf", _make_pdf(), save=True)
        self.assertTrue(Profile.objects.get(username="alice").cv_file)

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

        refreshed = Profile.objects.get(username="alice")
        self.assertFalse(refreshed.cv_file)

    def test_delete_removes_file_from_storage(self):
        field = Profile._meta.get_field("cv_file")
        with patch.object(field, "storage") as mock_storage:
            mock_storage.save.return_value = "cvs/alice.pdf"
            mock_storage.url.return_value = "/media/cvs/alice.pdf"
            mock_storage.generate_filename.side_effect = lambda n: n
            mock_storage.exists.return_value = False

            profile = Profile.objects.get(username="alice")
            profile.cv_file.save("alice.pdf", _make_pdf(), save=True)

            mock_storage.delete.reset_mock()
            self.client.post(self.url)

            # The file's storage backend must receive a delete call so the
            # S3 object goes away (issue #523: guard against rogue crawlers).
            self.assertTrue(
                mock_storage.delete.called,
                "Expected storage.delete to be called to remove S3 object",
            )

    def test_delete_when_no_cv_returns_ok(self):
        # No cv_file set on alice
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    def test_response_is_json(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp["Content-Type"], "application/json")
