"""Tests for syncing profile avatar to WordPress (#392).

These tests verify that when a user uploads a new avatar, the image
URL is sent to WordPress via a REST API call so that the WordPress
avatar stays in sync.
"""

import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.wordpress_sync import (
    sync_avatar_to_wordpress,
)


def _make_image():
    """Create a valid in-memory JPEG image."""
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(
        "test.jpg", buf.read(), content_type="image/jpeg"
    )


class SyncAvatarToWordPressTests(TestCase):
    """Tests for the sync_avatar_to_wordpress function."""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="synctest",
            name="Sync Test",
            profile_image="https://s3.example.com/media/profile_images/abc.jpg",
        )

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="https://hcommons.org/wp-json/idms/update-avatar",
        STATIC_API_BEARER="test-token-123",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_sends_post_with_correct_payload(self, mock_post):
        """Should POST username and image_url to the WordPress endpoint."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None

        result = sync_avatar_to_wordpress(
            "synctest",
            "https://s3.example.com/media/profile_images/abc.jpg",
        )

        self.assertTrue(result)
        call_kwargs = mock_post.call_args
        self.assertEqual(
            call_kwargs.kwargs["json"]["username"], "synctest"
        )
        self.assertEqual(
            call_kwargs.kwargs["json"]["image_url"],
            "https://s3.example.com/media/profile_images/abc.jpg",
        )

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="https://hcommons.org/wp-json/idms/update-avatar",
        STATIC_API_BEARER="test-token-123",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_sends_bearer_token(self, mock_post):
        """Should include the Bearer token in the Authorization header."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None

        sync_avatar_to_wordpress("synctest", "https://example.com/img.jpg")

        call_kwargs = mock_post.call_args
        self.assertEqual(
            call_kwargs.kwargs["headers"]["Authorization"],
            "Bearer test-token-123",
        )

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="",
        STATIC_API_BEARER="test-token-123",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_returns_false_when_url_not_configured(self, mock_post):
        """Should return False and not call requests when URL is empty."""
        result = sync_avatar_to_wordpress(
            "synctest", "https://example.com/img.jpg"
        )

        self.assertFalse(result)

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="https://hcommons.org/wp-json/idms/update-avatar",
        STATIC_API_BEARER="",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_returns_false_when_bearer_not_configured(self, mock_post):
        """Should return False and not call requests when bearer is empty."""
        result = sync_avatar_to_wordpress(
            "synctest", "https://example.com/img.jpg"
        )

        self.assertFalse(result)

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="https://hcommons.org/wp-json/idms/update-avatar",
        STATIC_API_BEARER="test-token-123",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_returns_false_on_request_exception(self, mock_post):
        """Should return False and log on request failure."""
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        result = sync_avatar_to_wordpress(
            "synctest", "https://example.com/img.jpg"
        )

        self.assertFalse(result)

    @override_settings(
        WORDPRESS_AVATAR_UPDATE_URL="https://hcommons.org/wp-json/idms/update-avatar",
        STATIC_API_BEARER="test-token-123",
    )
    @patch("knowledge_commons_profiles.newprofile.wordpress_sync.requests.post")
    def test_returns_false_on_http_error(self, mock_post):
        """Should return False on non-2xx HTTP response."""
        import requests

        mock_post.return_value.status_code = 500
        mock_post.return_value.raise_for_status.side_effect = (
            requests.exceptions.HTTPError("500 Server Error")
        )

        result = sync_avatar_to_wordpress(
            "synctest", "https://example.com/img.jpg"
        )

        self.assertFalse(result)


class AvatarUploadTriggersWordPressSyncTests(TestCase):
    """Tests that avatar upload view triggers WordPress sync."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.get_or_create(
            username="alice", defaults={"name": "Alice"}
        )
        self.url = reverse("upload_avatar")

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".sync_avatar_to_wordpress"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".index_profile_in_cc_search"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.avatars"
        ".default_storage"
    )
    def test_upload_avatar_calls_wordpress_sync(
        self, mock_storage, mock_index, mock_sync
    ):
        """Uploading an avatar should call sync_avatar_to_wordpress."""
        mock_storage.url.return_value = "/media/profile_images/new.jpg"
        self.client.login(username="alice", password="pass1234")

        self.client.post(self.url, {"image": _make_image()})

        mock_sync.assert_called_once_with(
            "alice", "/media/profile_images/new.jpg"
        )
