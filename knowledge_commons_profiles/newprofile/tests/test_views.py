from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import django.db
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.views.profile.htmx import blog_posts
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    mastodon_feed,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import mysql_data
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    profile_info,
)
from knowledge_commons_profiles.newprofile.views.profile.htmx import (
    works_deposits,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    edit_profile,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    my_profile,
)
from knowledge_commons_profiles.newprofile.views.profile.profile import (
    profile as profile_view,
)

STATUS_CODE_500 = 500
STATUS_CODE_302 = 302


class ProfileInfoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

        self.mock_profile = mock.MagicMock()
        self.mock_profile.name = "Test User"
        self.mock_profile.username = "testuser"
        self.mock_profile.title = "Professor"
        self.mock_profile.affiliation = "Test University"
        self.mock_profile.twitter = "@testuser"
        self.mock_profile.github = "testuser"
        self.mock_profile.email = "test@example.com"
        self.mock_profile.orcid = "0000-0000-0000-0000"
        self.mock_profile.mastodon = "@testuser@mastodon.social"
        self.mock_profile.profile_image = "https://example.com/profile.jpg"
        self.mock_profile.works_username = "works_testuser"
        self.mock_profile.publications = "<p>Sample publication</p>"
        self.mock_profile.projects = "Sample project"
        self.mock_profile.memberships = "Sample membership"
        self.mock_profile.institutional_or_other_affiliation = (
            "Test Institution"
        )
        self.mock_profile.external_sync_ids = "{}"
        self.mock_profile.is_member_of = '{"MLA": "True"}'

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    def test_profile_info(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        api_instance.profile = self.mock_profile
        api_instance.get_profile_info.return_value = self.mock_profile
        api_instance.get_academic_interests.return_value = [
            "Interest1",
            "Interest2",
        ]
        api_instance.get_education.return_value = ["Education1"]
        api_instance.get_about_user.return_value = "About user text"

        mock_api.return_value = api_instance

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
        self.assertIn(b"about user", response.content)


class WorksDepositsTests(django.test.TransactionTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    async def test_works_deposits(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.works_html = MagicMock(
            return_value="<div>Test works</div>"
        )

        # Create a proper awaitable mock
        mock_works_html = MagicMock()
        mock_works_html.return_value = {
            "Book": [{"html": "<div>Test works</div>"}]
        }
        # Use property() to make works_html a property that returns the
        # AsyncMock
        type(api_instance).works_html = property(
            lambda self: mock_works_html()
        )

        # Create request
        request = self.factory.get("/profile/testuser/works")
        request.user = self.user

        # Call view
        response = works_deposits(request, "testuser")

        # Assert API was called correctly
        mock_api.assert_called_once_with(
            request,
            "testuser",
            use_wordpress=False,
            create=False,
            works_citation_style=None,
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

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    def test_mastodon_feed_with_mastodon(self, mock_api):
        # Set up mock
        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.profile_info = {"mastodon": "mastodon-handle"}
        api_instance.mastodon_posts.latest_posts.return_value = [
            "Post1",
            "Post2",
        ]

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

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
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
        self.assertIn(b'class="hide', response.content)


class MyProfileTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.client = Client()

    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile.profile"
    )
    def test_my_profile_authenticated(self, mock_profile):
        # Set up mock
        mock_profile.return_value = "profile_response"

        # Create request
        request = self.factory.get("/my_profile")
        request.user = self.user

        # Call view
        response = my_profile(request)

        # Assert profile was called correctly
        mock_profile.assert_called_once_with(request, user="testuser")
        self.assertEqual(response, "profile_response")


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
)
class EditProfileTests(TestCase):
    """
    Tests for the edit_profile view
    """

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
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile.render"
    )
    def test_edit_profile_get(self, mock_render, mock_prefetch):
        # Set up mock
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        type(mock_user).left_order = PropertyMock(return_value="[]")
        type(mock_user).right_order = PropertyMock(return_value="[]")
        mock_queryset.get.return_value = mock_user

        # Create request
        request = self.factory.get("/edit_profile")
        request.user = self.user

        # Call view
        _ = edit_profile(request)

        # Assert prefetch was called correctly
        mock_prefetch.assert_called_with("academic_interests")
        mock_queryset.get.assert_called()

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    def test_edit_profile_post_invalid(self, mock_prefetch):
        # Set up mocks
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        type(mock_user).left_order = PropertyMock(return_value="[]")
        type(mock_user).right_order = PropertyMock(return_value="[]")
        mock_queryset.get.return_value = mock_user

        # Patch ProfileForm
        with patch(
            "knowledge_commons_profiles.newprofile."
            "views.profile.profile.ProfileForm"
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

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile.render"
    )
    def test_staff_can_edit_other_user(self, mock_render, mock_prefetch):
        staff_user = User.objects.create_user(
            username="staffuser", password="testpass", is_staff=True
        )
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        type(mock_user).left_order = PropertyMock(return_value="[]")
        type(mock_user).right_order = PropertyMock(return_value="[]")
        type(mock_user).username = PropertyMock(return_value="otheruser")
        mock_queryset.get.return_value = mock_user

        request = self.factory.get("/members/otheruser/edit-profile/")
        request.user = staff_user

        edit_profile(request, username="otheruser")

        mock_render.assert_called_once()

    def test_non_staff_cannot_edit_other_user(self):
        request = self.factory.get("/members/otheruser/edit-profile/")
        request.user = self.user

        with self.assertRaises(PermissionDenied):
            edit_profile(request, username="otheruser")

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile.render"
    )
    def test_non_staff_can_edit_own_profile(self, mock_render, mock_prefetch):
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        type(mock_user).left_order = PropertyMock(return_value="[]")
        type(mock_user).right_order = PropertyMock(return_value="[]")
        type(mock_user).username = PropertyMock(return_value="testuser")
        mock_queryset.get.return_value = mock_user

        request = self.factory.get("/edit-profile/")
        request.user = self.user

        edit_profile(request)

        mock_render.assert_called_once()

    @patch(
        "knowledge_commons_profiles.newprofile.models.Profile.objects."
        "prefetch_related"
    )
    @patch(
        "knowledge_commons_profiles.newprofile.views.profile.profile.render"
    )
    def test_staff_can_edit_own_profile_via_username(
        self, mock_render, mock_prefetch
    ):
        staff_user = User.objects.create_user(
            username="staffuser2", password="testpass", is_staff=True
        )
        mock_queryset = MagicMock()
        mock_prefetch.return_value = mock_queryset
        mock_user = MagicMock()
        type(mock_user).left_order = PropertyMock(return_value="[]")
        type(mock_user).right_order = PropertyMock(return_value="[]")
        type(mock_user).username = PropertyMock(return_value="staffuser2")
        mock_queryset.get.return_value = mock_user

        request = self.factory.get("/members/staffuser2/edit-profile/")
        request.user = staff_user

        edit_profile(request, username="staffuser2")

        mock_render.assert_called_once()


class BlogPostsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
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
        "knowledge_commons_profiles.newprofile.views.profile.htmx.API",
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

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.render")
    def test_mysql_data_success(self, mock_render, mock_api):
        # Set up mock
        mock_render = MagicMock()  # noqa: F841

        mock_profile = MagicMock()
        mock_profile.show_commons_groups = True

        api_instance = MagicMock()
        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {
            "name": "Test User",
            "profile": mock_profile,
        }
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

    @patch("knowledge_commons_profiles.newprofile.views.profile.htmx.API")
    def test_mysql_data_unauthenticated(self, mock_api):
        # Set up mock
        api_instance = MagicMock()

        mock_profile = MagicMock()
        mock_profile.show_commons_groups = True

        mock_api.return_value = api_instance
        api_instance.get_profile_info.return_value = {
            "name": "Test User",
            "profile": mock_profile,
        }
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
        "knowledge_commons_profiles.newprofile.views.profile.htmx.API",
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


class ProfileViewTests(TestCase):
    """Tests for the main profile() view, including the #326 regression.

    Uses the test Client so that responses go through the full URL resolver
    and template engine — a mocked render() would hide template errors.
    """

    PATCH_PREFIX = (
        "knowledge_commons_profiles.newprofile.views.profile.profile."
    )

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="testpass"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass", is_staff=True
        )

    def _make_mock_profile(self, username):
        mock_prof = MagicMock()
        mock_prof.username = username
        mock_prof.left_order = "[]"
        mock_prof.right_order = "[]"
        return mock_prof

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API")
    def test_anonymous_user_viewing_profile(
        self, mock_api, mock_profile_exists
    ):
        api_instance = MagicMock()
        api_instance.profile = self._make_mock_profile("testuser")
        mock_api.return_value = api_instance

        response = self.client.get("/members/testuser/")

        self.assertEqual(response.status_code, 200)

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API")
    def test_logged_in_user_viewing_own_profile(
        self, mock_api, mock_profile_exists
    ):
        api_instance = MagicMock()
        api_instance.profile = self._make_mock_profile("testuser")
        mock_api.return_value = api_instance

        self.client.login(username="testuser", password="testpass")
        response = self.client.get("/members/testuser/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["logged_in_user_is_profile"])
        self.assertIn(
            "/edit-profile/upload-avatar/",
            response.context["avatar_upload_url"],
        )
        self.assertIn(
            "/edit-profile/upload-cover/",
            response.context["cover_upload_url"],
        )

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API")
    def test_logged_in_user_viewing_other_profile(
        self, mock_api, mock_profile_exists
    ):
        """Regression test for #326: viewing another user's profile must use
        upload_cover_user / upload_avatar_user URL names."""
        api_instance = MagicMock()
        api_instance.profile = self._make_mock_profile("otheruser")
        mock_api.return_value = api_instance

        self.client.login(username="testuser", password="testpass")
        response = self.client.get("/members/otheruser/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["logged_in_user_is_profile"])
        self.assertIn(
            "/members/otheruser/edit-profile/upload-avatar/",
            response.context["avatar_upload_url"],
        )
        self.assertIn(
            "/members/otheruser/edit-profile/upload-cover/",
            response.context["cover_upload_url"],
        )

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API")
    def test_staff_user_viewing_own_profile(
        self, mock_api, mock_profile_exists
    ):
        api_instance = MagicMock()
        api_instance.profile = self._make_mock_profile("staffuser")
        mock_api.return_value = api_instance

        self.client.login(username="staffuser", password="testpass")
        response = self.client.get("/members/staffuser/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["logged_in_user_is_profile"])

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API")
    def test_staff_user_viewing_other_profile(
        self, mock_api, mock_profile_exists
    ):
        api_instance = MagicMock()
        api_instance.profile = self._make_mock_profile("otheruser")
        mock_api.return_value = api_instance

        self.client.login(username="staffuser", password="testpass")
        response = self.client.get("/members/otheruser/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["logged_in_user_is_profile"])
        self.assertIn(
            "/members/otheruser/edit-profile/upload-avatar/",
            response.context["avatar_upload_url"],
        )
        self.assertIn(
            "/members/otheruser/edit-profile/upload-cover/",
            response.context["cover_upload_url"],
        )

    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=False)
    def test_nonexistent_profile_returns_404(self, mock_profile_exists):
        response = self.client.get("/members/nosuchuser/")

        self.assertEqual(response.status_code, 404)

    @patch(PATCH_PREFIX + "render")
    @patch(PATCH_PREFIX + "profile_exists_or_has_been_created",
           return_value=True)
    @patch(PATCH_PREFIX + "API",
           side_effect=django.db.utils.OperationalError("connection refused"))
    def test_database_error_renders_with_fallback_context(
        self, mock_api, mock_profile_exists, mock_render
    ):
        # The DB-error fallback sets username="" which the template's
        # {% url %} tags can't resolve, so we mock render here and just
        # verify the view passes the right fallback context.
        # Uses RequestFactory to bypass middleware on the mock response.
        factory = RequestFactory()
        request = factory.get("/members/testuser/")
        request.user = self.user
        profile_view(request, user="testuser")

        mock_render.assert_called_once()
        ctx = mock_render.call_args.kwargs["context"]
        self.assertTrue(ctx["database_error"])
