import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from knowledge_commons_profiles.newprofile.models import CoverImage
from knowledge_commons_profiles.newprofile.models import Profile


def _make_image(fmt="JPEG", size=(200, 200), content_type="image/jpeg"):
    """Create a valid in-memory image and return a SimpleUploadedFile."""
    buf = io.BytesIO()
    Image.new("RGB", size, color="red").save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile("test.jpg", buf.read(), content_type=content_type)


class UploadAvatarAuthTests(TestCase):
    """Test authorization rules for upload_avatar."""

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
        # Create Profile rows for both users
        Profile.objects.create(username="alice", name="Alice")
        Profile.objects.create(username="bob", name="Bob")

        self.own_url = reverse("upload_avatar")
        self.bob_url = reverse(
            "upload_avatar_user", kwargs={"username": "bob"}
        )

    def test_anonymous_user_is_redirected(self):
        resp = self.client.post(self.own_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.get(self.own_url)
        self.assertEqual(resp.status_code, 405)

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_user_can_upload_own_avatar(self, mock_storage, mock_index):
        mock_storage.url.return_value = "/media/profile_images/abc.jpg"
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.own_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("url", data)

    def test_non_staff_cannot_upload_for_other_user(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.bob_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("Permission denied", data["error"])

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_staff_can_upload_for_other_user(self, mock_storage, mock_index):
        mock_storage.url.return_value = "/media/profile_images/abc.jpg"
        self.client.login(username="staffmember", password="pass1234")
        resp = self.client.post(self.bob_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_upload_updates_profile_image(self, mock_storage, mock_index):
        mock_storage.url.return_value = "/media/profile_images/new.jpg"
        self.client.login(username="alice", password="pass1234")
        self.client.post(self.own_url, {"image": _make_image()})
        profile = Profile.objects.get(username="alice")
        self.assertEqual(profile.profile_image, "/media/profile_images/new.jpg")


class UploadAvatarValidationTests(TestCase):
    """Test image validation for upload_avatar."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(username="alice", name="Alice")
        self.url = reverse("upload_avatar")
        self.client.login(username="alice", password="pass1234")

    def test_missing_image_returns_400(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("Invalid form data", data["error"])

    def test_non_image_file_returns_400(self):
        fake_file = SimpleUploadedFile(
            "readme.txt", b"just text", content_type="text/plain"
        )
        resp = self.client.post(self.url, {"image": fake_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_svg_content_type_rejected(self):
        # Create a valid raster image but claim it's SVG — Django's ImageField
        # rejects it at form validation, so we get "Invalid form data."
        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="PNG")
        buf.seek(0)
        svg_file = SimpleUploadedFile(
            "image.svg", buf.read(), content_type="image/svg+xml"
        )
        resp = self.client.post(self.url, {"image": svg_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_corrupt_image_returns_400(self):
        # Django's ImageField rejects corrupt bytes at form validation
        bad_file = SimpleUploadedFile(
            "broken.jpg", b"\x00\x01\x02", content_type="image/jpeg"
        )
        resp = self.client.post(self.url, {"image": bad_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_json_response_format_on_all_errors(self):
        """Every error response must be valid JSON with ok=False."""
        resp = self.client.post(self.url, {})
        self.assertEqual(resp["Content-Type"], "application/json")
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("error", data)


class UploadCoverAuthTests(TestCase):
    """Test authorization rules for upload_cover."""

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

        self.own_url = reverse("upload_cover")
        self.bob_url = reverse(
            "upload_cover_user", kwargs={"username": "bob"}
        )

    def test_anonymous_user_is_redirected(self):
        resp = self.client.post(self.own_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.get(self.own_url)
        self.assertEqual(resp.status_code, 405)

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_user_can_upload_own_cover(self, mock_storage):
        mock_storage.url.return_value = "/media/cover_images/abc.jpg"
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.own_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("url", data)

    def test_non_staff_cannot_upload_for_other_user(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(self.bob_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("Permission denied", data["error"])

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_staff_can_upload_for_other_user(self, mock_storage):
        mock_storage.url.return_value = "/media/cover_images/abc.jpg"
        self.client.login(username="staffmember", password="pass1234")
        resp = self.client.post(self.bob_url, {"image": _make_image()})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_upload_creates_cover_image_record(self, mock_storage):
        mock_storage.url.return_value = "/media/cover_images/new.jpg"
        self.client.login(username="alice", password="pass1234")
        self.client.post(self.own_url, {"image": _make_image()})
        profile = Profile.objects.get(username="alice")
        self.assertEqual(CoverImage.objects.filter(profile=profile).count(), 1)

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_upload_replaces_existing_cover_image(self, mock_storage):
        mock_storage.url.return_value = "/media/cover_images/v1.jpg"
        profile = Profile.objects.get(username="alice")
        CoverImage.objects.create(
            profile=profile, filename="old.jpg", file_path="old.jpg"
        )
        self.client.login(username="alice", password="pass1234")
        self.client.post(self.own_url, {"image": _make_image()})
        self.assertEqual(CoverImage.objects.filter(profile=profile).count(), 1)
        cover = CoverImage.objects.get(profile=profile)
        self.assertEqual(cover.filename, "/media/cover_images/v1.jpg")


class UploadCoverValidationTests(TestCase):
    """Test image validation for upload_cover."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(username="alice", name="Alice")
        self.url = reverse("upload_cover")
        self.client.login(username="alice", password="pass1234")

    def test_missing_image_returns_400(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_corrupt_image_returns_400(self):
        bad_file = SimpleUploadedFile(
            "broken.jpg", b"\x00\x01\x02", content_type="image/jpeg"
        )
        resp = self.client.post(self.url, {"image": bad_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])

    def test_svg_content_type_rejected(self):
        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="PNG")
        buf.seek(0)
        svg_file = SimpleUploadedFile(
            "image.svg", buf.read(), content_type="image/svg+xml"
        )
        resp = self.client.post(self.url, {"image": svg_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
