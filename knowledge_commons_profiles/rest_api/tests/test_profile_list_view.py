"""
Tests for the public members list endpoint (/api/v1/members/).

The list is anonymously readable, but anonymous callers must only ever see
the redacted view of a profile: the same private fields that the detail
endpoint withholds from them.
"""

from unittest import mock

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.authentication import (
    StaticBearerAuthentication,
)
from knowledge_commons_profiles.rest_api.sync import ExternalSync

TEST_TOKEN = "test-static-bearer-token"
PRIVATE_FIELDS = {"email", "emails"}

# keep the request middleware off Redis
LOCMEM_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


@override_settings(STATIC_API_BEARER=TEST_TOKEN, CACHES=LOCMEM_CACHES)
class TestProfileListViewAccess(TestCase):
    """Anonymous and authenticated access to the members list."""

    def setUp(self):
        # the authenticator reads its token once, at import time
        patcher = mock.patch.object(
            StaticBearerAuthentication, "static_token", TEST_TOKEN
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = APIClient()
        self.url = reverse("profiles_list_view")

        Profile.objects.create(
            username="martin_eve",
            name="Martin Paul Eve",
            email="martin@example.org",
            emails=["martin@example.org", "martin.alt@example.com"],
            orcid="0000-0002-5589-8511",
        )
        Profile.objects.create(
            username="mikethicke",
            name="Mike Thicke",
            email="mike@example.net",
            emails=["mike@example.net"],
        )

    def _get(self, token=None):
        headers = {}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        return self.client.get(self.url, headers=headers)

    def _results_by_username(self, response):
        return {row["username"]: row for row in response.json()["results"]}

    def test_anonymous_request_is_allowed(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)

    def test_anonymous_request_lists_profiles(self):
        results = self._results_by_username(self._get())

        self.assertEqual(set(results), {"martin_eve", "mikethicke"})
        self.assertEqual(results["martin_eve"]["name"], "Martin Paul Eve")
        self.assertEqual(results["martin_eve"]["orcid"], "0000-0002-5589-8511")

    def test_anonymous_response_omits_private_fields(self):
        results = self._results_by_username(self._get())

        for username, row in results.items():
            with self.subTest(username=username):
                self.assertFalse(PRIVATE_FIELDS & set(row))

    def test_anonymous_response_contains_no_email_addresses(self):
        body = self._get().content.decode()

        for address in (
            "martin@example.org",
            "martin.alt@example.com",
            "mike@example.net",
        ):
            with self.subTest(address=address):
                self.assertNotIn(address, body)

    def test_invalid_token_gets_the_redacted_list(self):
        response = self._get(token="not-the-right-token")

        self.assertEqual(response.status_code, 200)
        for row in response.json()["results"]:
            self.assertFalse(PRIVATE_FIELDS & set(row))
        self.assertNotIn("martin@example.org", response.content.decode())

    def test_authenticated_request_includes_private_fields(self):
        response = self._get(token=TEST_TOKEN)

        self.assertEqual(response.status_code, 200)
        results = self._results_by_username(response)
        self.assertEqual(results["martin_eve"]["email"], "martin@example.org")
        self.assertEqual(
            results["martin_eve"]["emails"],
            ["martin@example.org", "martin.alt@example.com"],
        )
        self.assertEqual(results["mikethicke"]["email"], "mike@example.net")

    def test_anonymous_fields_are_authenticated_fields_minus_private(self):
        anon = self._results_by_username(self._get())
        authed = self._results_by_username(self._get(token=TEST_TOKEN))

        self.assertEqual(
            set(anon["martin_eve"]),
            set(authed["martin_eve"]) - PRIVATE_FIELDS,
        )

    def test_anonymous_list_redacts_the_same_fields_as_anonymous_detail(self):
        """Whatever the detail endpoint hides from anon, the list hides."""
        detail_url = reverse("profiles_detail_view", args=["martin_eve"])
        with (
            mock.patch.object(ExternalSync, "sync"),
            mock.patch(
                "knowledge_commons_profiles.rest_api.serializers."
                "serializers.API"
            ) as wordpress_api,
            mock.patch(
                "knowledge_commons_profiles.rest_api.serializers."
                "serializers.get_external_memberships",
                return_value={},
            ),
        ):
            wordpress_api.return_value.get_profile_photo.return_value = ""
            wordpress_api.return_value.get_groups.return_value = []

            anon_detail = self.client.get(detail_url).json()
            authed_detail = self.client.get(
                detail_url, headers={"authorization": f"Bearer {TEST_TOKEN}"}
            ).json()

        hidden_from_anon_detail = set(authed_detail) - set(anon_detail)
        anon_list_row = self._results_by_username(self._get())["martin_eve"]

        self.assertTrue(hidden_from_anon_detail)
        self.assertFalse(hidden_from_anon_detail & set(anon_list_row))

    def test_redaction_holds_on_later_pages(self):
        Profile.objects.bulk_create(
            Profile(
                username=f"user{i:03d}",
                name=f"User {i}",
                email=f"user{i:03d}@example.org",
                emails=[f"user{i:03d}@example.org"],
            )
            for i in range(30)
        )

        first = self._get().json()
        self.assertTrue(first["next"])
        second = self.client.get(first["next"])

        self.assertEqual(second.status_code, 200)
        rows = second.json()["results"]
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(PRIVATE_FIELDS & set(row))
        self.assertNotIn("@example.", second.content.decode())
