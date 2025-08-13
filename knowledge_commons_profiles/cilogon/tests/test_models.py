"""
Comprehensive unit tests for CILogon models
"""

import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.newprofile.models import Profile

from .test_base import CILogonTestBase


class SubAssociationModelTests(CILogonTestBase):
    """Test cases for SubAssociation model"""

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pw")
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def test_sub_association_creation(self):
        """Test creating a SubAssociation"""
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        self.assertEqual(sub_assoc.sub, "cilogon_sub_123")
        self.assertEqual(sub_assoc.profile, self.profile)
        self.assertIn("testuser", str(sub_assoc))
        self.assertIn("cilogon_sub_123", str(sub_assoc))

    def test_sub_association_unique_constraint(self):
        """Test that sub field enforces uniqueness"""
        SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        # Create another profile
        profile2 = Profile.objects.create(
            username="testuser2", email="test2@example.com", name="Test User 2"
        )

        # Should not allow duplicate sub
        with self.assertRaises(IntegrityError):
            SubAssociation.objects.create(
                sub="cilogon_sub_123", profile=profile2
            )

    def test_sub_association_cascade_delete(self):
        """Test that SubAssociation is deleted when Profile is deleted"""
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        # Delete the profile
        self.profile.delete()

        # SubAssociation should be deleted too
        with self.assertRaises(SubAssociation.DoesNotExist):
            SubAssociation.objects.get(id=sub_assoc.id)

    def test_sub_association_null_profile(self):
        """Test SubAssociation with null profile"""
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=None
        )

        self.assertEqual(sub_assoc.sub, "cilogon_sub_123")
        self.assertIsNone(sub_assoc.profile)

    def test_sub_association_max_length_validation(self):
        """Test sub field max length validation"""
        long_sub = "a" * 256  # Exceeds max_length of 255

        with self.assertRaises(ValidationError):
            sub_assoc = SubAssociation(sub=long_sub, profile=self.profile)
            sub_assoc.full_clean()

    def test_sub_association_empty_sub(self):
        """Test SubAssociation with empty sub"""
        sub_assoc = SubAssociation.objects.create(sub="", profile=self.profile)

        self.assertEqual(sub_assoc.sub, "")
        self.assertEqual(sub_assoc.profile, self.profile)

    def test_sub_association_meta_attributes(self):
        """Test model meta attributes"""
        self.assertEqual(
            SubAssociation._meta.verbose_name, "CI Logon Association"
        )
        self.assertEqual(
            SubAssociation._meta.verbose_name_plural, "CI Logon Associations"
        )

    def test_sub_association_query_by_sub(self):
        """Test querying SubAssociation by sub"""
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        found_assoc = SubAssociation.objects.get(sub="cilogon_sub_123")
        self.assertEqual(found_assoc, sub_assoc)

    def test_sub_association_query_by_profile(self):
        """Test querying SubAssociation by profile"""
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        found_assoc = SubAssociation.objects.get(profile=self.profile)
        self.assertEqual(found_assoc, sub_assoc)


class TokenUserAgentAssociationsModelTests(CILogonTestBase):
    """Test cases for TokenUserAgentAssociations model"""

    def test_token_association_creation(self):
        """Test creating a TokenUserAgentAssociations"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Mozilla/5.0 Test Browser",
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            app="knowledge_commons",
            user_name="testuser",
        )

        self.assertEqual(assoc.user_agent, "Mozilla/5.0 Test Browser")
        self.assertEqual(assoc.access_token, "access_token_123")
        self.assertEqual(assoc.refresh_token, "refresh_token_456")
        self.assertEqual(assoc.app, "knowledge_commons")
        self.assertEqual(assoc.user_name, "testuser")
        self.assertIsNotNone(assoc.created_at)

    def test_token_association_auto_timestamp(self):
        """Test that created_at is automatically set"""
        before_creation = timezone.now()

        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Test Browser", app="testapp", user_name="testuser"
        )

        after_creation = timezone.now()

        self.assertGreaterEqual(assoc.created_at, before_creation)
        self.assertLessEqual(assoc.created_at, after_creation)

    def test_token_association_optional_tokens(self):
        """Test creating association with optional token fields"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Test Browser",
            app="testapp",
            user_name="testuser",
            # access_token and refresh_token are optional
        )

        self.assertIsNone(assoc.access_token)
        self.assertIsNone(assoc.refresh_token)

    def test_token_association_blank_tokens(self):
        """Test creating association with blank token fields"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Test Browser",
            access_token="",
            refresh_token="",
            app="testapp",
            user_name="testuser",
        )

        self.assertEqual(assoc.access_token, "")
        self.assertEqual(assoc.refresh_token, "")

    def test_token_association_long_tokens(self):
        """Test creating association with very long tokens"""
        long_token = "a" * 1000  # Very long token

        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Test Browser",
            access_token=long_token,
            refresh_token=long_token,
            app="testapp",
            user_name="testuser",
        )

        self.assertEqual(assoc.access_token, long_token)
        self.assertEqual(assoc.refresh_token, long_token)

    def test_token_association_str_representation(self):
        """Test string representation of TokenUserAgentAssociations"""
        assoc = TokenUserAgentAssociations.objects.create(
            user_agent="Test Browser",
            access_token="access_123",
            refresh_token="refresh_456",
            app="testapp",
            user_name="testuser",
        )

        str_repr = str(assoc)
        self.assertIn("testapp", str_repr)
        self.assertIn("refresh_456", str_repr)
        self.assertIn("access_123", str_repr)
        self.assertIn("Test Browser", str_repr)

    def test_token_association_filtering_by_user_agent(self):
        """Test filtering associations by user agent"""
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser1", app="testapp", user_name="testuser"
        )
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser2", app="testapp", user_name="testuser"
        )

        browser1_assocs = TokenUserAgentAssociations.objects.filter(
            user_agent="Browser1"
        )
        self.assertEqual(len(browser1_assocs), 1)

    def test_token_association_filtering_by_user_name(self):
        """Test filtering associations by username"""
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="testapp", user_name="user1"
        )
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="testapp", user_name="user2"
        )

        user1_assocs = TokenUserAgentAssociations.objects.filter(
            user_name="user1"
        )
        self.assertEqual(len(user1_assocs), 1)

    def test_token_association_filtering_by_app(self):
        """Test filtering associations by app"""
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="app1", user_name="testuser"
        )
        TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="app2", user_name="testuser"
        )

        app1_assocs = TokenUserAgentAssociations.objects.filter(app="app1")
        self.assertEqual(len(app1_assocs), 1)

    def test_token_association_ordering_by_created_at(self):
        """Test ordering associations by creation time"""
        assoc1 = TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="testapp", user_name="testuser"
        )

        # Create second association slightly later
        assoc2 = TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="testapp", user_name="testuser"
        )

        ordered_assocs = TokenUserAgentAssociations.objects.order_by(
            "created_at"
        )
        self.assertEqual(list(ordered_assocs), [assoc1, assoc2])

    def test_token_association_bulk_operations(self):
        """Test bulk operations on token associations"""
        # Create multiple associations
        associations = []
        for i in range(5):
            assoc = TokenUserAgentAssociations(
                user_agent=f"Browser{i}", app="testapp", user_name="testuser"
            )
            associations.append(assoc)

        # Bulk create
        TokenUserAgentAssociations.objects.bulk_create(associations)

        # Verify all were created
        self.assertEqual(TokenUserAgentAssociations.objects.count(), 5)

        # Bulk delete
        TokenUserAgentAssociations.objects.filter(app="testapp").delete()

        # Verify all were deleted
        self.assertEqual(TokenUserAgentAssociations.objects.count(), 0)


class EmailVerificationModelTests(CILogonTestBase):
    """Test cases for EmailVerification model"""

    def setUp(self):
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def test_email_verification_creation(self):
        """Test creating an EmailVerification"""
        secret_uuid = str(uuid.uuid4())
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=secret_uuid,
            profile=self.profile,
        )

        self.assertEqual(verification.sub, "cilogon_sub_123")
        self.assertEqual(verification.secret_uuid, secret_uuid)
        self.assertEqual(verification.profile, self.profile)
        self.assertIsNotNone(verification.created_at)

    def test_email_verification_auto_timestamp(self):
        """Test that created_at is automatically set"""
        before_creation = timezone.now()

        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        after_creation = timezone.now()

        self.assertGreaterEqual(verification.created_at, before_creation)
        self.assertLessEqual(verification.created_at, after_creation)

    def test_email_verification_null_profile(self):
        """Test EmailVerification with null profile"""
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123", secret_uuid=str(uuid.uuid4()), profile=None
        )

        self.assertEqual(verification.sub, "cilogon_sub_123")
        self.assertIsNone(verification.profile)

    def test_email_verification_cascade_delete(self):
        """Test that EmailVerification is deleted when Profile is deleted"""
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        # Delete the profile
        self.profile.delete()

        # EmailVerification should be deleted too
        with self.assertRaises(EmailVerification.DoesNotExist):
            EmailVerification.objects.get(id=verification.id)

    def test_email_verification_str_representation(self):
        """Test string representation of EmailVerification"""
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        str_repr = str(verification)
        self.assertIn("cilogon_sub_123", str_repr)
        self.assertIn("Test User", str_repr)

    def test_email_verification_unique_secret_generation(self):
        """Test that each verification gets a unique secret"""
        verification1 = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        # Create another profile for second verification
        profile2 = Profile.objects.create(
            username="testuser2", email="test2@example.com", name="Test User 2"
        )

        verification2 = EmailVerification.objects.create(
            sub="cilogon_sub_456",
            secret_uuid=str(uuid.uuid4()),
            profile=profile2,
        )

        self.assertNotEqual(
            verification1.secret_uuid, verification2.secret_uuid
        )

    def test_email_verification_query_by_sub_and_secret(self):
        """Test querying EmailVerification by sub and secret"""
        secret_uuid = str(uuid.uuid4())
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=secret_uuid,
            profile=self.profile,
        )

        found_verification = EmailVerification.objects.get(
            sub="cilogon_sub_123", secret_uuid=secret_uuid
        )
        self.assertEqual(found_verification, verification)

    def test_email_verification_expiration_logic(self):
        """Test email verification expiration logic"""
        # Create verification with past timestamp
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        # Manually set created_at to past time
        past_time = timezone.now() - timedelta(days=7)
        verification.created_at = past_time
        verification.save()

        # Query for expired verifications (older than 24 hours)
        cutoff_time = timezone.now() - timedelta(hours=24)
        expired_verifications = EmailVerification.objects.filter(
            created_at__lt=cutoff_time
        )

        self.assertIn(verification, expired_verifications)

    def test_email_verification_cleanup_expired(self):
        """Test cleanup of expired email verifications"""
        # Create multiple verifications with different ages
        recent_verification = EmailVerification.objects.create(
            sub="cilogon_sub_recent",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        old_verification = EmailVerification.objects.create(
            sub="cilogon_sub_old",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        # Manually set old verification to past time
        old_time = timezone.now() - timedelta(days=7)
        old_verification.created_at = old_time
        old_verification.save()

        # Delete expired verifications (older than 24 hours)
        cutoff_time = timezone.now() - timedelta(hours=24)
        expired_count = EmailVerification.objects.filter(
            created_at__lt=cutoff_time
        ).delete()[0]

        self.assertEqual(expired_count, 1)

        # Recent verification should still exist
        self.assertTrue(
            EmailVerification.objects.filter(
                id=recent_verification.id
            ).exists()
        )

        # Old verification should be deleted
        self.assertFalse(
            EmailVerification.objects.filter(id=old_verification.id).exists()
        )

    def test_email_verification_max_length_validation(self):
        """Test field max length validation"""
        long_sub = "a" * 256  # Exceeds max_length of 255
        long_secret = "a" * 256  # Exceeds max_length of 255

        with self.assertRaises(ValidationError):
            verification = EmailVerification(
                sub=long_sub,
                secret_uuid=str(uuid.uuid4()),
                profile=self.profile,
            )
            verification.full_clean()

        with self.assertRaises(ValidationError):
            verification = EmailVerification(
                sub="cilogon_sub_123",
                secret_uuid=long_secret,
                profile=self.profile,
            )
            verification.full_clean()


class ModelIntegrationTests(CILogonTestBase):
    """Integration tests for CILogon models working together"""

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pw")
        self.profile = Profile.objects.create(
            username="testuser", email="test@example.com", name="Test User"
        )

    def test_complete_authentication_flow_models(self):
        """Test complete authentication flow using all models"""
        # 1. Start with email verification
        secret_uuid = str(uuid.uuid4())
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=secret_uuid,
            profile=self.profile,
        )

        # 2. After verification, create SubAssociation
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        # 3. Create token associations for session management
        TokenUserAgentAssociations.objects.create(
            user_agent="Mozilla/5.0 Test Browser",
            access_token="access_token_123",
            refresh_token="refresh_token_456",
            app="knowledge_commons",
            user_name="testuser",
        )

        # Verify all models are properly linked
        self.assertEqual(verification.sub, sub_assoc.sub)
        self.assertEqual(verification.profile, sub_assoc.profile)

        # Clean up verification after successful association
        verification.delete()

        # SubAssociation should remain
        self.assertTrue(
            SubAssociation.objects.filter(id=sub_assoc.id).exists()
        )

    def test_user_logout_cleanup(self):
        """Test model cleanup during user logout"""
        # Create associations for user
        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        TokenUserAgentAssociations.objects.create(
            user_agent="Browser1",
            access_token="token1",
            refresh_token="refresh1",
            app="knowledge_commons",
            user_name="testuser",
        )

        TokenUserAgentAssociations.objects.create(
            user_agent="Browser2",
            access_token="token2",
            refresh_token="refresh2",
            app="knowledge_commons",
            user_name="testuser",
        )

        # Simulate logout cleanup - delete token associations but keep
        # SubAssociation
        TokenUserAgentAssociations.objects.filter(
            user_name="testuser"
        ).delete()

        # SubAssociation should remain for future logins
        self.assertTrue(
            SubAssociation.objects.filter(id=sub_assoc.id).exists()
        )

    def test_profile_deletion_cascade(self):
        """Test cascading deletion when profile is deleted"""
        # Create all related objects
        verification = EmailVerification.objects.create(
            sub="cilogon_sub_123",
            secret_uuid=str(uuid.uuid4()),
            profile=self.profile,
        )

        sub_assoc = SubAssociation.objects.create(
            sub="cilogon_sub_123", profile=self.profile
        )

        TokenUserAgentAssociations.objects.create(
            user_agent="Browser", app="knowledge_commons", user_name="testuser"
        )

        # Delete the profile
        self.profile.delete()

        # EmailVerification and SubAssociation should be deleted (CASCADE)
        self.assertFalse(
            EmailVerification.objects.filter(id=verification.id).exists()
        )
        self.assertFalse(
            SubAssociation.objects.filter(id=sub_assoc.id).exists()
        )

    @transaction.atomic
    def test_atomic_association_creation(self):
        """Test atomic creation of associations to prevent inconsistency"""

        class SimulatedError(Exception):
            """Custom exception for testing atomic transactions"""

        def _raise_simulated_error():
            """Helper function to raise simulated error"""
            error_msg = "Simulated error"
            raise SimulatedError(error_msg)

        try:
            with transaction.atomic():
                # Create sub association
                SubAssociation.objects.create(
                    sub="atomic_test_sub", profile=self.profile
                )

                # Simulate an error that would rollback the transaction
                _raise_simulated_error()

        except SimulatedError:
            # Transaction should have been rolled back
            pass

        # Verify no associations were created due to rollback
        self.assertFalse(
            SubAssociation.objects.filter(sub="atomic_test_sub").exists()
        )
