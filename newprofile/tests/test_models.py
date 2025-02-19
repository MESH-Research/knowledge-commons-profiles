"""
Test suite for models
"""

# pylint: disable=protected-access, no-member, import-error
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from newprofile.models import (
    Profile,
    AcademicInterest,
    CoverImage,
    ProfileImage,
    WpPost,
    WpBlog,
    WpProfileData,
    WpProfileFields,
    WpUser,
    WpBpGroupMember,
    WpBpGroup,
    WpUserMeta,
    WpTermTaxonomy,
    WpTermRelationships,
    WpBpFollow,
    WpBpUserBlogMeta,
    WpBpActivity,
    WpBpActivityMeta,
    WpBpNotification,
    WpPostSubTable,
)


class WpModelsMetaTests(TestCase):
    """Test meta configurations for WordPress models"""

    def test_wp_models_managed_false(self):
        """Test that all WordPress models have managed=False"""
        wp_models = [
            WpPost,
            WpBlog,
            WpProfileData,
            WpProfileFields,
            WpUser,
            WpBpGroupMember,
            WpBpGroup,
            WpUserMeta,
            WpTermTaxonomy,
            WpTermRelationships,
            WpBpFollow,
            WpBpUserBlogMeta,
            WpBpActivity,
            WpBpActivityMeta,
            WpBpNotification,
            WpPostSubTable,
        ]

        for model in wp_models:
            self.assertFalse(
                model._meta.managed,
                f"WordPress model {model.__name__} should have managed=False",
            )

    def test_wp_models_db_table(self):
        """Test that WordPress models have correct db_table values"""
        db_table_map = {
            WpPost: "wp_posts",
            WpBlog: "wp_blogs",
            WpProfileData: "wp_bp_xprofile_data",
            WpProfileFields: "wp_bp_xprofile_fields",
            WpUser: "wp_users",
            WpBpGroupMember: "wp_bp_groups_members",
            WpBpGroup: "wp_bp_groups",
            WpUserMeta: "wp_usermeta",
            WpTermTaxonomy: "wp_term_taxonomy",
            WpTermRelationships: "wp_term_relationships",
            WpBpFollow: "wp_bp_follow",
            WpBpUserBlogMeta: "wp_bp_user_blogs_blogmeta",
            WpBpActivity: "wp_bp_activity",
            WpBpActivityMeta: "wp_bp_activity_meta",
            WpBpNotification: "wp_bp_notifications",
            WpPostSubTable: "wp_posts",
        }

        for model, expected_table in db_table_map.items():
            self.assertEqual(
                model._meta.db_table,
                expected_table,
                f"WordPress model {model.__name__} should have db_table={expected_table}",
            )


class ProfileModelTests(TestCase):
    """Test suite for the Profile model"""

    def setUp(self):
        """Set up test data"""
        self.academic_interest = AcademicInterest.objects.create(
            text="Digital Humanities"
        )

        self.profile = Profile.objects.create(
            name="Test User",
            username="testuser",
            central_user_id=12345,
            title="Professor",
            affiliation="Test University",
            twitter="@testuser",
            github="testuser",
            email="test@example.com",
            orcid="0000-0001-2345-6789",
            mastodon="@test@mastodon.social",
            bluesky="@test.bsky.social",
            profile_image="https://example.com/image.jpg",
            works_username="testworks",
            about_user="About me text",
            education="PhD in Testing",
        )
        self.profile.academic_interests.add(self.academic_interest)

    def tearDown(self):
        """Clean up resources after tests"""
        # Remove any uploaded files
        if hasattr(self, "profile") and self.profile.cv_file:
            storage = self.profile.cv_file.storage
            if storage.exists(self.profile.cv_file.name):
                storage.delete(self.profile.cv_file.name)

    def test_profile_creation(self):
        """Test that a profile can be created with expected values"""
        self.assertEqual(self.profile.name, "Test User")
        self.assertEqual(self.profile.username, "testuser")
        self.assertEqual(self.profile.central_user_id, 12345)
        self.assertEqual(self.profile.academic_interests.count(), 1)
        self.assertEqual(
            self.profile.academic_interests.first().text, "Digital Humanities"
        )

    def test_profile_str_representation(self):
        """Test the string representation of a Profile instance"""
        self.assertEqual(str(self.profile), "Test User")

    def test_default_visibility_settings(self):
        """Test that visibility settings have correct defaults"""
        # All visibility settings should default to True
        visibility_fields = [
            field.name
            for field in Profile._meta.fields
            if field.name.startswith("show_")
        ]

        for field in visibility_fields:
            self.assertTrue(
                getattr(self.profile, field),
                f"Default value for {field} should be True",
            )

    def test_profile_cv_file_upload(self):
        """Test CV file upload functionality"""
        cv_file = SimpleUploadedFile(
            "test_cv.pdf", b"file content", content_type="application/pdf"
        )

        self.profile.cv_file = cv_file
        self.profile.save()

        # Check that the file is saved and path is as expected
        self.assertTrue(self.profile.cv_file.name.startswith("cvs/"))
        self.assertTrue(self.profile.cv_file.name.endswith(".pdf"))


class AcademicInterestTests(TestCase):
    """Test suite for the AcademicInterest model"""

    def test_academic_interest_creation(self):
        """Test creating an academic interest"""
        interest = AcademicInterest.objects.create(text="Machine Learning")
        self.assertEqual(interest.text, "Machine Learning")
        self.assertEqual(str(interest), "Machine Learning")


class WpUserTests(TestCase):
    """Test suite for the WpUser model"""

    def test_wp_user_str_representation(self):
        """Test string representation of WpUser"""
        user = WpUser(
            id=1,
            user_login="wpuser",
            user_email="wp@example.com",
            display_name="WordPress User",
        )
        self.assertEqual(str(user), "wpuser")


class WpPostTests(TestCase):
    """Test suite for the WpPost model"""

    def setUp(self):
        """Mock necessary related objects"""
        self.user_mock = mock.MagicMock(spec=WpUser)
        self.user_mock.id = 1

        # Patch the foreign key relationship
        with mock.patch("django.db.models.ForeignKey.related_model", WpUser):
            self.post = WpPost(
                id=101,
                post_author_id=1,
                post_title="Test Post Title",
                post_content="Test content",
                post_status="publish",
            )

    def test_wp_post_str_representation(self):
        """Test string representation of WpPost"""
        self.assertEqual(str(self.post), "Test Post Title")

    def test_wp_post_user_voice_defaults(self):
        """Test default values for user voice fields"""
        self.assertEqual(self.post.user_voice_slug, "general")
        self.assertEqual(self.post.user_voice_active, False)
        self.assertEqual(self.post.user_voice_alignment, "right")
        self.assertEqual(self.post.user_voice_color, "00BCBA")


class WpBpGroupTests(TestCase):
    """Test suite for the WpBpGroup model"""

    def test_group_status_choices(self):
        """Test that group status choices are defined correctly"""
        expected_choices = [
            ("public", "Public"),
            ("private", "Private"),
            ("hidden", "Hidden"),
        ]

        status_field = WpBpGroup._meta.get_field("status")
        self.assertEqual(status_field.choices, expected_choices)


class WpBpNotificationTests(TestCase):
    """Test suite for the WpBpNotification model"""

    @mock.patch("newprofile.notifications.BuddyPressNotification")
    def test_notification_string_methods(self, mock_bp_notification):
        """Test notification string representation methods"""
        # Set up the mock
        notification_instance = mock.MagicMock()
        mock_bp_notification.return_value = notification_instance
        notification_instance.get_string.return_value = (
            "Test notification message"
        )
        notification_instance.__str__.return_value = "Test notification"

        notification = WpBpNotification(
            id=1,
            user_id=1,
            item_id=100,
            component_name="test_component",
            component_action="test_action",
        )

        # Test __str__ method
        self.assertEqual(str(notification), "Test notification")

        # Test get_string method
        self.assertEqual(
            notification.get_string("testuser"), "Test notification message"
        )
        notification_instance.get_string.assert_called_with(
            username="testuser"
        )

        # Test get_short_string method
        notification.get_short_string("testuser")
        notification_instance.get_string.assert_called_with(
            short=True, username="testuser"
        )


class ModelRelationshipTests(TestCase):
    """Test suite for model relationships"""

    def test_profile_academic_interest_relationship(self):
        """Test M2M relationship between Profile and AcademicInterest"""
        interest1 = AcademicInterest.objects.create(text="AI")
        interest2 = AcademicInterest.objects.create(text="Machine Learning")

        profile = Profile.objects.create(
            name="Researcher", username="researcher"
        )

        profile.academic_interests.add(interest1, interest2)

        # Test from profile to interests
        self.assertEqual(profile.academic_interests.count(), 2)
        self.assertIn(interest1, profile.academic_interests.all())

        # Test from interest to profiles
        self.assertEqual(interest1.profiles.count(), 1)
        self.assertIn(profile, interest1.profiles.all())

    def test_wp_user_group_membership_relationship(self):
        """Test relationship between WpUser and WpBpGroupMember"""
        # This test verifies the related_name is set up correctly
        user_field = WpBpGroupMember._meta.get_field("user")
        self.assertEqual(
            user_field.remote_field.related_name, "group_memberships"
        )


class ImageModelsTests(TestCase):
    """Test suite for image-related models"""

    def setUp(self):
        """Set up test data"""
        self.profile = Profile.objects.create(
            name="Image Test User", username="imageuser"
        )

        self.profile_image = ProfileImage.objects.create(
            profile=self.profile,
            thumb="thumbnails/test.jpg",
            full="images/test.jpg",
        )

        self.cover_image = CoverImage.objects.create(
            profile=self.profile,
            filename="cover.jpg",
            file_path="covers/cover.jpg",
        )

    def test_profile_image_creation(self):
        """Test creating a profile image"""
        self.assertEqual(self.profile_image.profile, self.profile)
        self.assertEqual(self.profile_image.thumb, "thumbnails/test.jpg")
        self.assertEqual(self.profile_image.full, "images/test.jpg")
        self.assertIsNotNone(self.profile_image.created_at)
        self.assertIsNotNone(self.profile_image.updated_at)

    def test_cover_image_creation(self):
        """Test creating a cover image"""
        self.assertEqual(self.cover_image.profile, self.profile)
        self.assertEqual(self.cover_image.filename, "cover.jpg")
        self.assertEqual(self.cover_image.file_path, "covers/cover.jpg")
        self.assertIsNotNone(self.cover_image.created_at)
        self.assertIsNotNone(self.cover_image.updated_at)


class WpModelFieldTests(TestCase):
    """Test suite for specific field configurations in WordPress models"""

    def test_wp_post_fields(self):
        """Test field configuration for WpPost model"""
        # Test primary key field
        id_field = WpPost._meta.get_field("id")
        self.assertTrue(id_field.primary_key)
        self.assertEqual(id_field.db_column, "ID")

        # Test indexed fields
        post_name_field = WpPost._meta.get_field("post_name")
        self.assertTrue(post_name_field.db_index)

        post_parent_field = WpPost._meta.get_field("post_parent")
        self.assertTrue(post_parent_field.db_index)

        # Test specified model indexes
        indexes = [index.fields for index in WpPost._meta.indexes]
        self.assertIn(["post_type", "post_status", "post_date", "id"], indexes)

    def test_wp_user_fields(self):
        """Test field configuration for WpUser model"""
        # Test unique field
        login_field = WpUser._meta.get_field("user_login")
        self.assertTrue(login_field.unique)

        # Test default values
        user_status_field = WpUser._meta.get_field("user_status")
        self.assertEqual(user_status_field.default, 0)
