"""
Tests for the ``normalise_emails`` management command.
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from knowledge_commons_profiles.newprofile.models import Profile


class NormaliseEmailsCommandTests(TestCase):
    def _call(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command(
            "normalise_emails",
            *args,
            stdout=out,
            stderr=err,
            **kwargs,
        )
        return out.getvalue(), err.getvalue()

    def test_primary_email_lowercased(self):
        profile = Profile.objects.create(
            username="alpha",
            email="Mixed@Example.COM",
            name="Alpha",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.email, "mixed@example.com")

    def test_secondary_emails_lowercased(self):
        profile = Profile.objects.create(
            username="beta",
            email="primary@example.com",
            emails=["Foo@Example.com", "BAR@example.com"],
            name="Beta",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(
            profile.emails,
            ["bar@example.com", "foo@example.com"],
        )

    def test_secondary_emails_deduplicated_after_lowercase(self):
        profile = Profile.objects.create(
            username="gamma",
            email="primary@example.com",
            emails=["Foo@Example.com", "foo@example.com", "FOO@example.com"],
            name="Gamma",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.emails, ["foo@example.com"])

    def test_linked_django_user_email_lowercased(self):
        Profile.objects.create(
            username="delta",
            email="Mixed@Example.com",
            name="Delta",
        )
        User.objects.create(username="delta", email="Mixed@Example.com")

        self._call()

        user = User.objects.get(username="delta")
        self.assertEqual(user.email, "mixed@example.com")

    def test_already_lowercase_profile_left_alone(self):
        profile = Profile.objects.create(
            username="epsilon",
            email="clean@example.com",
            emails=["other@example.com"],
            name="Epsilon",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.email, "clean@example.com")
        self.assertEqual(profile.emails, ["other@example.com"])

    def test_dry_run_does_not_persist_changes(self):
        profile = Profile.objects.create(
            username="zeta",
            email="MiXeD@Example.com",
            emails=["AlSo@Example.com"],
            name="Zeta",
        )
        self._call("--dry-run")
        profile.refresh_from_db()
        self.assertEqual(profile.email, "MiXeD@Example.com")
        self.assertEqual(profile.emails, ["AlSo@Example.com"])

    def test_command_is_idempotent(self):
        profile = Profile.objects.create(
            username="eta",
            email="Mixed@Example.com",
            emails=["Foo@Example.com"],
            name="Eta",
        )
        self._call()
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.email, "mixed@example.com")
        self.assertEqual(profile.emails, ["foo@example.com"])

    def test_handles_empty_emails_field(self):
        profile = Profile.objects.create(
            username="theta",
            email="Mixed@Example.com",
            emails=[],
            name="Theta",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.email, "mixed@example.com")
        self.assertEqual(profile.emails, [])

    def test_handles_blank_primary_email(self):
        profile = Profile.objects.create(
            username="iota",
            email="",
            emails=["Foo@Example.com"],
            name="Iota",
        )
        self._call()
        profile.refresh_from_db()
        self.assertEqual(profile.email, "")
        self.assertEqual(profile.emails, ["foo@example.com"])
