"""
Tests that email comparisons across the cilogon app treat incoming emails
case-insensitively. Stored emails are normalised to lowercase by the
``normalise_emails`` management command and by the views themselves.
"""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.views import _add_secondary_email
from knowledge_commons_profiles.cilogon.views import _make_email_primary
from knowledge_commons_profiles.cilogon.views import _remove_secondary_email
from knowledge_commons_profiles.cilogon.views import association
from knowledge_commons_profiles.cilogon.views import validate_form
from knowledge_commons_profiles.newprofile.models import Profile

from .test_base import CILogonTestBase


def _request_with_messages(factory, path="/", method="GET", data=None):
    if method.upper() == "POST":
        request = factory.post(path, data or {})
    else:
        request = factory.get(path)
    request.session = SessionStore()
    request.session.create()
    request._messages = FallbackStorage(request)
    return request


class AssociationCaseInsensitiveLookupTests(CILogonTestBase):
    """The /associate flow must match an existing profile regardless of case."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.profile = Profile.objects.create(
            username="testuser",
            email="canonical@example.com",
            name="Test User",
        )

    def test_primary_email_match_is_case_insensitive(self):
        request = _request_with_messages(
            self.factory,
            "/auth/association/",
            method="POST",
            data={"email": "Canonical@Example.COM"},
        )
        request.user = AnonymousUser()

        userinfo = {"sub": "cilogon_sub_assoc_1", "email": "x@example.com"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
                return_value=(True, userinfo),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.send_knowledge_commons_email",
                return_value=True,
            ),
        ):
            association(request)

        self.assertTrue(
            EmailVerification.objects.filter(
                sub="cilogon_sub_assoc_1",
                profile=self.profile,
            ).exists(),
        )

    def test_secondary_email_match_is_case_insensitive(self):
        self.profile.emails = ["alt@example.com"]
        self.profile.save()

        request = _request_with_messages(
            self.factory,
            "/auth/association/",
            method="POST",
            data={"email": "ALT@Example.com"},
        )
        request.user = AnonymousUser()

        userinfo = {"sub": "cilogon_sub_assoc_2", "email": "x@example.com"}
        with (
            patch(
                "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
                return_value=(True, userinfo),
            ),
            patch(
                "knowledge_commons_profiles.cilogon.views.send_knowledge_commons_email",
                return_value=True,
            ),
        ):
            association(request)

        self.assertTrue(
            EmailVerification.objects.filter(
                sub="cilogon_sub_assoc_2",
                profile=self.profile,
            ).exists(),
        )


class ValidateFormCaseInsensitiveTests(CILogonTestBase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.profile = Profile.objects.create(
            username="existing",
            email="taken@example.com",
            emails=["secondary@example.com"],
            name="Existing",
        )

    def _request(self):
        request = self.factory.post("/register/")
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        return request

    def test_duplicate_primary_detected_case_insensitively(self):
        request = self._request()
        errored = validate_form(
            "TAKEN@Example.com",
            "New User",
            request,
            "newuser",
        )
        self.assertTrue(errored)

    def test_duplicate_secondary_detected_case_insensitively(self):
        request = self._request()
        errored = validate_form(
            "Secondary@EXAMPLE.com",
            "New User",
            request,
            "newuser",
        )
        self.assertTrue(errored)


class SecondaryEmailHelperCaseTests(CILogonTestBase):
    """The internal helpers that operate on Profile.emails must be case-safe."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.profile = Profile.objects.create(
            username="helper",
            email="primary@example.com",
            emails=["secondary@example.com"],
            name="Helper",
        )

    def _request(self, data):
        request = self.factory.post("/foo/", data)
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        return request

    def test_add_secondary_rejects_mixed_case_duplicate_of_primary(self):
        request = self._request({"new_email": "PRIMARY@example.com"})
        result = _add_secondary_email(self.profile, request)
        self.assertFalse(result)

    def test_add_secondary_rejects_mixed_case_duplicate_of_existing_secondary(
        self,
    ):
        # Another profile has the email as a secondary
        Profile.objects.create(
            username="other",
            email="other@example.com",
            emails=["already@example.com"],
            name="Other",
        )
        request = self._request({"new_email": "Already@Example.com"})
        result = _add_secondary_email(self.profile, request)
        self.assertFalse(result)

    def test_remove_secondary_handles_mixed_case_input(self):
        request = self._request({"email_remove": "SECONDARY@example.com"})
        _remove_secondary_email(self.profile, request)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.emails, [])

    def test_make_primary_handles_mixed_case_input(self):
        request = self._request({"email_primary": "SECONDARY@example.com"})
        with patch(
            "knowledge_commons_profiles.cilogon.views.hcommons_update_user_email_in_mailchimp"
        ), patch(
            "knowledge_commons_profiles.cilogon.views.sync_email_to_wordpress"
        ):
            _make_email_primary(self.profile, request)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.email, "secondary@example.com")
        self.assertIn("primary@example.com", self.profile.emails)
        self.assertNotIn("secondary@example.com", self.profile.emails)
