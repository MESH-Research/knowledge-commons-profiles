"""
Tests for hcommons_update_user_email_in_mailchimp().
"""

import hashlib
from unittest.mock import patch

from django.test import SimpleTestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_update_user_email_in_mailchimp,
)

MAILCHIMP_SETTINGS = {
    "MAILCHIMP_API_KEY": "test-key",
    "MAILCHIMP_DC": "us1",
    "MAILCHIMP_LIST_ID": "list123",
}


@override_settings(**MAILCHIMP_SETTINGS)
class UpdateUserEmailInMailchimpTests(SimpleTestCase):
    """Tests for updating an existing subscriber's email in Mailchimp."""

    @patch(
        "knowledge_commons_profiles.newprofile.mailchimp"
        ".hcommons_mailchimp_request"
    )
    def test_updates_existing_subscribed_member(self, mock_request):
        """When the old email is a subscribed member, PATCH the new email."""
        mock_request.side_effect = [
            # First call: GET lookup returns existing subscribed member
            {
                "email_address": "old@example.com",
                "status": "subscribed",
                "id": "abc123",
            },
            # Second call: PATCH returns updated member
            {
                "email_address": "new@example.com",
                "status": "subscribed",
                "id": "abc123",
            },
        ]

        result = hcommons_update_user_email_in_mailchimp(
            "old@example.com", "new@example.com"
        )

        self.assertTrue(result)
        self.assertEqual(mock_request.call_count, 2)

        # Verify the PATCH call
        patch_call = mock_request.call_args_list[1]
        subscriber_hash = hashlib.md5(  # noqa: S324
            "old@example.com".lower().encode()
        ).hexdigest()
        self.assertIn(subscriber_hash, patch_call[0][0])
        self.assertEqual(patch_call[0][1], "PATCH")
        self.assertEqual(
            patch_call[1]["params"]["email_address"], "new@example.com"
        )

    @patch(
        "knowledge_commons_profiles.newprofile.mailchimp"
        ".hcommons_mailchimp_request"
    )
    def test_does_nothing_when_subscriber_not_found(self, mock_request):
        """When the old email is not in Mailchimp, do nothing."""
        mock_request.return_value = None  # Not found

        result = hcommons_update_user_email_in_mailchimp(
            "old@example.com", "new@example.com"
        )

        self.assertFalse(result)
        # Only the lookup call, no PATCH
        self.assertEqual(mock_request.call_count, 1)

    @patch(
        "knowledge_commons_profiles.newprofile.mailchimp"
        ".hcommons_mailchimp_request"
    )
    def test_does_nothing_when_subscriber_not_subscribed(self, mock_request):
        """When old email is unsubscribed/archived, do nothing."""
        mock_request.return_value = {
            "email_address": "old@example.com",
            "status": "unsubscribed",
            "id": "abc123",
        }

        result = hcommons_update_user_email_in_mailchimp(
            "old@example.com", "new@example.com"
        )

        self.assertFalse(result)
        self.assertEqual(mock_request.call_count, 1)

    @patch(
        "knowledge_commons_profiles.newprofile.mailchimp"
        ".hcommons_mailchimp_request"
    )
    def test_returns_false_when_patch_fails(self, mock_request):
        """When the PATCH call fails, return False."""
        mock_request.side_effect = [
            # Lookup succeeds
            {
                "email_address": "old@example.com",
                "status": "subscribed",
                "id": "abc123",
            },
            # PATCH fails
            None,
        ]

        result = hcommons_update_user_email_in_mailchimp(
            "old@example.com", "new@example.com"
        )

        self.assertFalse(result)

    @override_settings(MAILCHIMP_LIST_ID="", MAILCHIMP_API_KEY="")
    def test_returns_false_when_mailchimp_not_configured(self):
        """When Mailchimp settings are missing, return False early."""
        result = hcommons_update_user_email_in_mailchimp(
            "old@example.com", "new@example.com"
        )

        self.assertFalse(result)

    @patch(
        "knowledge_commons_profiles.newprofile.mailchimp"
        ".hcommons_mailchimp_request"
    )
    def test_does_nothing_when_emails_are_same(self, mock_request):
        """When old and new emails are identical, skip the API call."""
        result = hcommons_update_user_email_in_mailchimp(
            "same@example.com", "same@example.com"
        )

        self.assertFalse(result)
        mock_request.assert_not_called()
