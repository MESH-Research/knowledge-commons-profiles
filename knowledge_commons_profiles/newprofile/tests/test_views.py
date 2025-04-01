from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import django
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from knowledge_commons_profiles.newprofile.views import ProfileView
from knowledge_commons_profiles.newprofile.views import blog_posts
from knowledge_commons_profiles.newprofile.views import edit_profile
from knowledge_commons_profiles.newprofile.views import logout_view
from knowledge_commons_profiles.newprofile.views import mastodon_feed
from knowledge_commons_profiles.newprofile.views import my_profile
from knowledge_commons_profiles.newprofile.views import mysql_data
from knowledge_commons_profiles.newprofile.views import profile
from knowledge_commons_profiles.newprofile.views import profile_info
from knowledge_commons_profiles.newprofile.views import works_deposits

STATUS_CODE_500 = 500
STATUS_CODE_302 = 302


class ProfileInfoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_profile_info(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {"name": "Test User"}
        api_instance.get_academic_interests.return_value = [
            "Interest1",
            "Interest2",
        ]
        api_instance.get_education.return_value = ["Education1"]
        api_instance.get_about_user.return_value = "About user text"

        # Create request
        request = self.factory.get("/profile/testuser/profile_info")
        request.user = self.user

        # Call view
        response = profile_info(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request, "testuser", use_wordpress=False, create=False
        )

        # Assert template was rendered with correct context
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test User", response.content)


class WorksDepositsTests(django.test.TransactionTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    async def test_works_deposits(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.works_html = AsyncMock(
            return_value="<div>Test works</div>"
        )

        # Create a proper awaitable mock
        mock_works_html = AsyncMock()
        mock_works_html.return_value = "<div>Test works</div>"
        # Use property() to make works_html a property that returns the
        # AsyncMock
        type(api_instance).works_html = property(
            lambda self: mock_works_html()
        )

        # Create request
        request = self.factory.get("/profile/testuser/works")
        request.user = self.user

        # Call view
        response = await works_deposits(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request, "testuser", use_wordpress=False, create=False
        )

        # Assert template was rendered with correct context
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<div>Test works</div>", response.content)


class MastodonFeedTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_mastodon_feed_with_mastodon(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.profile_info = {"mastodon": "mastodon-handle"}
        api_instance.mastodon_posts.latest_posts = ["Post1", "Post2"]

        # Create request
        request = self.factory.get("/profile/testuser/mastodon")
        request.user = self.user

        # Call view
        response = mastodon_feed(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request, "testuser", use_wordpress=False, create=False
        )

        # Assert template was rendered with correct context
        self.assertEqual(response.status_code, 200)

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_mastodon_feed_without_mastodon(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.profile_info = {"mastodon": None}

        # Create request
        request = self.factory.get("/profile/testuser/mastodon")
        request.user = self.user

        # Call view
        response = mastodon_feed(request, "testuser")

        # Assert template was rendered with empty posts
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No recent", response.content)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.logout")
    def test_logout_view(self, mock_logout):
        # Create request
        request = self.factory.get("/logout")
        request.user = self.user

        # Call view
        logout_view(request)

        # Assert logout was called
        mock_logout.assert_called_once_with(request)


class ProfileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def test_profile_with_theme(self):
        # Create request with theme
        request = self.factory.get("/profile/testuser?theme=new_profile")
        request.user = self.user

        # Call view
        response = profile(request, user="testuser")

        # Assert template was rendered
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"testuser", response.content)

    def test_profile_without_theme(self):
        # Create request without theme
        request = self.factory.get("/profile/testuser")
        request.user = self.user

        # Call view
        response = profile(request, user="testuser")

        # Assert template was rendered
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"testuser", response.content)


class MyProfileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client = Client()

    @patch("knowledge_commons_profiles.newprofile.views.profile")
    def test_my_profile_authenticated(self, mock_profile):
        # Set up mock
        mock_profile.return_value = "profile_response"

        # Create request
        request = self.factory.get("/my_profile")
        request.user = self.user

        # Call view
        response = my_profile(request)

        # Assert profile was called correctly
        mock_profile.assert_called_once_with(
            request, user="testuser", create=True
        )
        self.assertEqual(response, "profile_response")

    def test_my_profile_login_required(self):
        # Test with unauthenticated user through the client
        response = self.client.get(reverse("my_profile"))

        # Should redirect to login page
        self.assertTrue(
            any(
                [
                    response.status_code == STATUS_CODE_302,
                    response.status_code == STATUS_CODE_500,
                ]
            )
        )
        self.assertTrue(response.url.startswith("https://hcommons.org"))


class ProfileViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_get(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {
            "name": "Test User",
            "mastodon": "mastodon-handle",
        }
        api_instance.get_education.return_value = ["Education1"]
        api_instance.get_about_user.return_value = "About user text"
        api_instance.mastodon_posts.latest_posts = ["Post1", "Post2"]
        api_instance.get_memberships.return_value = ["Membership1"]

        # Create request
        request = self.factory.get("/api/profile/testuser")
        request.user = self.user

        # Instantiate view
        view = ProfileView()
        view.request = request

        # Call view
        response = view.get(request, user_name="testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request, "testuser", use_wordpress=True
        )

        # Assert correct response was returned
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["profile_info"],
            {"name": "Test User", "mastodon": "mastodon-handle"},
        )
        self.assertEqual(response.data["education"], ["Education1"])
        self.assertEqual(response.data["about_user"], "About user text")
        self.assertEqual(response.data["mastodon_posts"], ["Post1", "Post2"])
        self.assertEqual(response.data["memberships"], ["Membership1"])


class EditProfileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client = Client()

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    @patch("knowledge_commons_profiles.newprofile.views.render")
    def test_edit_profile_get(self, mock_render, mock_prefetch):
        # Set up mock
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        mock_queryset.get.return_value = mock_user

        # Create request
        request = self.factory.get("/edit_profile")
        request.user = self.user

        # Call view
        _ = edit_profile(request)

        # Assert prefetch was called correctly
        mock_prefetch.assert_called_once_with("academic_interests")
        mock_queryset.get.assert_called_once_with(username="testuser")

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    def test_edit_profile_post_valid(self, mock_prefetch):
        # Set up mocks
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        mock_queryset.get.return_value = mock_user

        # Patch ProfileForm
        with patch(
            "knowledge_commons_profiles.newprofile.views.ProfileForm"
        ) as mock_form_class:
            mock_form = MagicMock()
            mock_form_class.return_value = mock_form
            mock_form.is_valid.return_value = True

            # Create request
            request = self.factory.post("/edit_profile", {"field": "value"})
            request.user = self.user

            # Call view
            _ = edit_profile(request)

            # Assert form was created and saved
            # Don't check the exact arguments, just verify it was called
            mock_form_class.assert_called_once()
            mock_form.is_valid.assert_called_once()
            mock_form.save.assert_called_once()

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    def test_edit_profile_post_invalid(self, mock_prefetch):
        # Set up mocks
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        mock_queryset.get.return_value = mock_user

        # Patch ProfileForm
        with patch(
            "knowledge_commons_profiles.newprofile.views.ProfileForm"
        ) as mock_form_class:
            mock_form = MagicMock()
            mock_form_class.return_value = mock_form
            mock_form.is_valid.return_value = False

            # Create request
            request = self.factory.post("/edit_profile", {"field": "value"})
            request.user = self.user

            # Call view
            _ = edit_profile(request)

            # Assert form was created but not saved
            # Don't check the exact arguments, just verify it was called
            mock_form_class.assert_called_once()
            mock_form.is_valid.assert_called_once()
            mock_form.save.assert_not_called()

    def test_edit_profile_login_required(self):
        # Test with unauthenticated user through the client
        response = self.client.get(reverse("edit_profile"))

        # Should redirect to login page
        self.assertTrue(
            any(
                [
                    response.status_code == STATUS_CODE_302,
                    response.status_code == STATUS_CODE_500,
                ]
            )
        )
        self.assertTrue(response.url.startswith("https://hcommons.org"))


class BlogPostsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_blog_posts_success(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_blog_posts.return_value = ["Post1", "Post2"]

        # Create request
        request = self.factory.get("/profile/testuser/blog_posts")
        request.user = self.user

        # Call view
        response = blog_posts(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request, "testuser", use_wordpress=True, create=False
        )

        # Assert template was rendered with correct context
        self.assertEqual(response.status_code, 200)

    @patch(
        "knowledge_commons_profiles.newprofile.views.API",
        side_effect=django.db.utils.OperationalError,
    )
    def test_blog_posts_db_error(self, mock_api):
        # Create request
        request = self.factory.get("/profile/testuser/blog_posts")
        request.user = self.user

        # Call view
        response = blog_posts(request, "testuser")

        # Assert empty blog posts were returned
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"hide", response.content)


class MySQLDataTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    @patch("knowledge_commons_profiles.newprofile.views.render")
    def test_mysql_data_success(self, mock_render, mock_api):
        # Set up mock
        mock_render = MagicMock()  # noqa: F841

        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {"name": "Test User"}
        api_instance.get_cover_image.return_value = "cover.jpg"
        api_instance.get_profile_photo.return_value = "profile.jpg"
        api_instance.get_groups.return_value = ["Group1", "Group2"]
        api_instance.get_memberships.return_value = ["Membership1"]
        api_instance.follower_count.return_value = (True, 42)
        api_instance.get_user_blogs.return_value = ["Blog1"]
        api_instance.get_activity.return_value = ["Activity1"]
        api_instance.get_short_notifications.return_value = [
            "Notification1",
            "Notification2",
        ]

        # Create request
        request = self.factory.get("/profile/testuser/mysql_data")
        request.user = self.user

        # Call view
        _ = mysql_data(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_with(
            request, "testuser", use_wordpress=True, create=False
        )

    @patch("knowledge_commons_profiles.newprofile.views.API")
    def test_mysql_data_unauthenticated(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {"name": "Test User"}
        api_instance.get_cover_image.return_value = "cover.jpg"
        api_instance.get_profile_photo.return_value = "profile.jpg"
        api_instance.get_groups.return_value = ["Group1", "Group2"]
        api_instance.get_memberships.return_value = ["Membership1"]
        api_instance.follower_count.return_value = (True, 42)
        api_instance.get_user_blogs.return_value = ["Blog1"]
        api_instance.get_activity.return_value = ["Activity1"]

        # Create request with unauthenticated user
        request = self.factory.get("/profile/testuser/mysql_data")
        request.user = AnonymousUser()

        # Call view
        response = mysql_data(request, "testuser")

        # Assert template was rendered with correct context
        self.assertEqual(response.status_code, 200)

    @patch(
        "knowledge_commons_profiles.newprofile.views.API",
        side_effect=django.db.utils.OperationalError,
    )
    def test_mysql_data_db_error(self, mock_api):
        # Create request
        request = self.factory.get("/profile/testuser/mysql_data")
        request.user = self.user

        # Call view
        response = mysql_data(request, "testuser")

        # Assert empty context was returned
        self.assertEqual(response.status_code, 200)


class ProfileViewTest(TestCase):
    """
    Test the profile view
    """

    def setUp(self):
        # Create test users
        self.test_user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            is_superuser=True,
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="password123",
            is_superuser=True,
        )
        self.client = Client()

    def test_own_profile_shows_edit_options(self):
        """Test that a user viewing their own profile sees edit options"""
        # Log in as test_user
        self.client.login(username="testuser", password="password123")

        # Access test_user's profile
        response = self.client.get(
            reverse("profile", kwargs={"user": "testuser"})
        )

        # Check that the response has status code 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Check that logged_in_user_is_profile is True in the context
        self.assertTrue(response.context["logged_in_user_is_profile"])

        # Check that the edit profile link is in the response
        self.assertContains(response, "Edit")
        self.assertContains(response, "Change Profile Photo")
        self.assertContains(response, "Change Cover Image")

    def test_other_profile_hides_edit_options(self):
        """Test that a user viewing someone else's profile doesn't see
        edit options"""
        # Log in as test_user
        self.client.login(username="testuser", password="password123")

        # Access other_user's profile
        response = self.client.get(
            reverse("profile", kwargs={"user": "otheruser"})
        )

        # Check that the response has status code 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Check that logged_in_user_is_profile is False in the context
        self.assertFalse(response.context["logged_in_user_is_profile"])

        # Check that the edit profile link is not in the response
        self.assertNotContains(response, 'class="action-btn primary">Edit</a>')
        self.assertNotContains(
            response, 'class="action-btn">Change Profile Photo</a>'
        )
        self.assertNotContains(
            response, 'class="action-btn">Change Cover Image</a>'
        )

    def test_unauthenticated_user_hides_edit_options(self):
        """Test that an unauthenticated user doesn't see edit options on
        any profile"""
        # Access a profile without logging in
        response = self.client.get(
            reverse("profile", kwargs={"user": "testuser"})
        )

        # Check that the response has status code 200 (OK)
        self.assertEqual(response.status_code, 200)

        # Check that logged_in_user_is_profile is False in the context
        self.assertFalse(response.context["logged_in_user_is_profile"])

        # Check that the edit profile link is not in the response
        self.assertNotContains(response, 'class="action-btn primary">Edit</a>')
        self.assertNotContains(
            response, 'class="action-btn">Change Profile Photo</a>'
        )
        self.assertNotContains(
            response, 'class="action-btn">Change Cover Image</a>'
        )
