"""
Tests for the public members list endpoint (/api/v1/members/).

The list is anonymously readable, but anonymous callers must only ever see
the redacted view of a profile: the same private fields that the detail
endpoint withholds from them.

The list is also network aware: on a network host it only contains the
members of that network, exactly as the /members/ directory does.
"""

import json
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


SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}
DISPLAY_NAMES = {
    "stemed+": "STEMEd+ Commons",
    "hastac": "HASTAC",
    "mla": "Modern Language Association",
}
BASE_HOST = "profile.hcommons.org"
STEMED_HOST = f"stemedplus.{BASE_HOST}"
MLA_HOST = f"MLA.{BASE_HOST}"


@override_settings(
    STATIC_API_BEARER=TEST_TOKEN,
    CACHES=LOCMEM_CACHES,
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    NETWORK_SUBDOMAIN_BASE_DOMAINS=[BASE_HOST],
    NETWORK_SUBDOMAIN_IGNORED=["www"],
    NETWORK_HOST_ALIASES={"profile.stemedplus.org": "stemedplus"},
)
class TestProfileListViewNetworkScoping(TestCase):
    """The members list is scoped to the network of the requesting host."""

    def setUp(self):
        patcher = mock.patch.object(
            StaticBearerAuthentication, "static_token", TEST_TOKEN
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = APIClient()
        self.url = reverse("profiles_list_view")

        self._make("alice", is_member_of={"STEMED+": True, "MLA": False})
        self._make("bob", is_member_of={"MLA": True})
        self._make("carol", role_overrides=["STEMED+"])
        self._make("dave")
        self._make("erin", is_member_of={"STEMED+": False})
        self._make("frank", role_overrides=["MLA"])

    def _make(self, username, is_member_of=None, role_overrides=None, **kw):
        kw.setdefault("name", username.title())
        return Profile.objects.create(
            username=username,
            email=f"{username}@example.org",
            emails=[f"{username}@example.org"],
            is_member_of=json.dumps(is_member_of) if is_member_of else None,
            role_overrides=role_overrides or [],
            **kw,
        )

    def _get(self, host, token=None, url=None):
        headers = {"host": host}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        return self.client.get(url or self.url, headers=headers)

    def _all_usernames(self, host, token=None):
        """Walk every page of the list on a host, collecting usernames."""
        usernames = []
        url = self.url
        while url:
            response = self._get(host, token=token, url=url)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            usernames.extend(row["username"] for row in body["results"])
            url = body["next"]
        return usernames

    def test_root_domain_lists_every_member(self):
        self.assertEqual(
            set(self._all_usernames(BASE_HOST)),
            {"alice", "bob", "carol", "dave", "erin", "frank"},
        )

    def test_network_subdomain_lists_only_that_networks_members(self):
        self.assertEqual(
            set(self._all_usernames(STEMED_HOST)), {"alice", "carol"}
        )

    def test_other_network_subdomain_lists_only_its_role_holders(self):
        self.assertEqual(set(self._all_usernames(MLA_HOST)), {"bob", "frank"})

    def test_dedicated_network_host_is_scoped_like_a_subdomain(self):
        self.assertEqual(
            set(self._all_usernames("profile.stemedplus.org")),
            {"alice", "carol"},
        )

    def test_network_with_no_members_gives_an_empty_list(self):
        response = self._get(f"hastac.{BASE_HOST}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_unknown_network_host_is_not_found(self):
        response = self._get(f"notanetwork.{BASE_HOST}")

        self.assertEqual(response.status_code, 404)

    def test_ignored_subdomain_is_treated_as_the_root_domain(self):
        self.assertEqual(len(self._all_usernames(f"www.{BASE_HOST}")), 6)

    def test_anonymous_network_list_is_redacted(self):
        response = self._get(STEMED_HOST)

        rows = response.json()["results"]
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(PRIVATE_FIELDS & set(row))
        self.assertNotIn("@example.org", response.content.decode())

    def test_authenticated_network_list_is_scoped_and_unredacted(self):
        response = self._get(STEMED_HOST, token=TEST_TOKEN)

        rows = {row["username"]: row for row in response.json()["results"]}
        self.assertEqual(set(rows), {"alice", "carol"})
        self.assertEqual(rows["alice"]["email"], "alice@example.org")
        self.assertEqual(rows["carol"]["emails"], ["carol@example.org"])

    def test_network_scoping_holds_across_pages(self):
        for i in range(30):
            self._make(f"mla{i:03d}", is_member_of={"MLA": True})
            self._make(f"other{i:03d}", is_member_of={"STEMED+": True})

        usernames = self._all_usernames(MLA_HOST)

        self.assertEqual(
            sorted(usernames),
            sorted(["bob", "frank"] + [f"mla{i:03d}" for i in range(30)]),
        )

    def test_network_list_matches_the_members_directory(self):
        """The API and /members/ agree on who belongs to a network."""
        with mock.patch(
            "knowledge_commons_profiles.newprofile.views.members."
            "get_profile_photo",
            return_value="",
        ):
            directory = self.client.get(
                "/members/", headers={"host": STEMED_HOST}
            )
        directory_usernames = {
            profile.username for profile in directory.context["profiles"]
        }

        self.assertTrue(directory_usernames)
        self.assertEqual(
            set(self._all_usernames(STEMED_HOST)), directory_usernames
        )

    def test_network_member_without_a_display_name_is_still_listed(self):
        self._make("nameless", is_member_of={"MLA": True}, name="")

        self.assertIn("nameless", self._all_usernames(MLA_HOST))
        self.assertIn("nameless", self._all_usernames(BASE_HOST))
