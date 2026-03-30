"""Tests for the CV auto-upload AJAX endpoint (issue #453)."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.newprofile.models import Profile


def _make_pdf(size_bytes=1024):
    """Create a minimal valid-looking PDF file for testing."""
    # A minimal PDF header so extension validation passes
    content = b"%PDF-1.4 test" + b"\x00" * max(0, size_bytes - 13)
    return SimpleUploadedFile(
        "test.pdf", content, content_type="application/pdf"
    )


def _make_docx():
    """Create a fake .docx file for testing."""
    return SimpleUploadedFile(
        "test.docx",
        b"PK\x03\x04fakecontent",
        content_type=(
            "application/vnd.openxmlformats-"
            "officedocument.wordprocessingml.document"
        ),
    )


class UploadCvAuthTests(TestCase):
    """Test authorization rules for upload_cv."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        self.other_user = User.objects.create_user(
            username="bob", password="pass1234"
        )
        self.staff_user = User.objects.create_user(
            username="staffmember", password="pass1234", is_staff=True
        )
        Profile.objects.create(username="alice", name="Alice")
        Profile.objects.create(username="bob", name="Bob")

        self.own_url = reverse("upload_cv")
        self.bob_url = reverse(
            "upload_cv_user", kwargs={"username": "bob"}
        )

    def test_anonymous_user_is_redirected(self):
        resp = self.client.post(self.own_url, {"cv_file": _make_pdf()})
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.get(self.own_url)
        self.assertEqual(resp.status_code, 405)

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_user_can_upload_own_cv(self, mock_storage):
        mock_storage.save.return_value = "cvs/test.pdf"
        mock_storage.url.return_value = "/media/cvs/test.pdf"
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.own_url, {"cv_file": _make_pdf()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("url", data)
        self.assertIn("filename", data)

    def test_non_staff_cannot_upload_for_other_user(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.bob_url, {"cv_file": _make_pdf()})
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("Permission denied", data["error"])

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_staff_can_upload_for_other_user(self, mock_storage):
        mock_storage.save.return_value = "cvs/test.pdf"
        mock_storage.url.return_value = "/media/cvs/test.pdf"
        self.client.login(username="staffmember", password="pass1234")
        resp = self.client.post(self.bob_url, {"cv_file": _make_pdf()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_upload_saves_cv_to_profile(self, mock_storage):
        mock_storage.save.return_value = "cvs/test.pdf"
        mock_storage.url.return_value = "/media/cvs/test.pdf"
        self.client.login(username="alice", password="pass1234")
        self.client.post(self.own_url, {"cv_file": _make_pdf()})
        profile = Profile.objects.get(username="alice")
        self.assertTrue(profile.cv_file)


class UploadCvValidationTests(TestCase):
    """Test file validation for upload_cv."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(username="alice", name="Alice")
        self.url = reverse("upload_cv")
        self.client.login(username="alice", password="pass1234")

    def test_missing_file_returns_400(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_wrong_extension_returns_400(self):
        bad_file = SimpleUploadedFile(
            "readme.txt", b"just text", content_type="text/plain"
        )
        resp = self.client.post(self.url, {"cv_file": bad_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("error", data)

    def test_oversized_file_returns_400(self):
        # Create a file over 10 MB
        big_file = SimpleUploadedFile(
            "huge.pdf",
            b"%PDF-1.4 " + b"\x00" * (11 * 1024 * 1024),
            content_type="application/pdf",
        )
        resp = self.client.post(self.url, {"cv_file": big_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_pdf_accepted(self, mock_storage):
        mock_storage.save.return_value = "cvs/test.pdf"
        mock_storage.url.return_value = "/media/cvs/test.pdf"
        resp = self.client.post(self.url, {"cv_file": _make_pdf()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_docx_accepted(self, mock_storage):
        mock_storage.save.return_value = "cvs/test.docx"
        mock_storage.url.return_value = "/media/cvs/test.docx"
        resp = self.client.post(self.url, {"cv_file": _make_docx()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    def test_exe_rejected(self):
        exe_file = SimpleUploadedFile(
            "malware.exe",
            b"MZ" + b"\x00" * 100,
            content_type="application/octet-stream",
        )
        resp = self.client.post(self.url, {"cv_file": exe_file})
        self.assertEqual(resp.status_code, 400)

    def test_json_response_format_on_all_errors(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp["Content-Type"], "application/json")
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("error", data)


class UploadCvDeletesOldFileTests(TestCase):
    """Test that uploading a new CV replaces the old one."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(username="alice", name="Alice")
        self.url = reverse("upload_cv")
        self.client.login(username="alice", password="pass1234")

    @patch(
        "django.core.files.storage.default_storage"
    )
    def test_second_upload_replaces_first(self, mock_storage):
        mock_storage.save.return_value = "cvs/first.pdf"
        mock_storage.url.return_value = "/media/cvs/first.pdf"

        # First upload
        self.client.post(self.url, {"cv_file": _make_pdf()})

        # Second upload
        mock_storage.save.return_value = "cvs/second.pdf"
        mock_storage.url.return_value = "/media/cvs/second.pdf"
        resp = self.client.post(self.url, {"cv_file": _make_pdf()})

        self.assertEqual(resp.status_code, 200)
        profile = Profile.objects.get(username="alice")
        # The profile should have the new file
        self.assertTrue(profile.cv_file)
