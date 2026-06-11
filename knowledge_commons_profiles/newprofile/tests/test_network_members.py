# tests for the /network/<network_name>/members/ listing
import json

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.views import members
from knowledge_commons_profiles.newprofile.views.members import (
    resolve_network_display_name,
)
from knowledge_commons_profiles.newprofile.views.members import (
    resolve_network_name,
)

SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}
DISPLAY_NAMES = {
    "up": "Association of University Presses",
    "mla": "Modern Language Association",
    "stemed+": "STEM Ed+",
    "hastac": "HASTAC",
    "paginet": "PAGINET",
}


def _make_profile(username, name=None, is_member_of=None, role_overrides=None):
    return Profile.objects.create(
        username=username,
        name=name if name is not None else username.title(),
        is_member_of=json.dumps(is_member_of) if is_member_of else None,
        role_overrides=role_overrides or [],
    )


@override_settings(KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS)
class ResolveNetworkNameTests(TestCase):
    def test_known_slug_maps_to_society_name(self):
        self.assertEqual(resolve_network_name("stemedplus"), "STEMED+")

    def test_known_slug_lookup_is_case_insensitive(self):
        self.assertEqual(resolve_network_name("StemEdPlus"), "STEMED+")

    def test_unknown_slug_is_used_literally(self):
        self.assertEqual(resolve_network_name("up"), "up")


@override_settings(NETWORK_DISPLAY_NAMES=DISPLAY_NAMES)
class ResolveNetworkDisplayNameTests(TestCase):
    def test_mapped_network_gets_display_name(self):
        self.assertEqual(
            resolve_network_display_name("up"),
            "Association of University Presses",
        )

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(
            resolve_network_display_name("MLA"),
            "Modern Language Association",
        )

    def test_unmapped_network_falls_back_to_canonical_name(self):
        self.assertEqual(
            resolve_network_display_name("NOSUCHNET"), "NOSUCHNET"
        )


@override_settings(
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
)
class NetworkDisplayNameInListingTests(TestCase):
    def setUp(self):
        Profile.objects.create(
            username="grace",
            name="Grace",
            is_member_of=json.dumps({"UP": True}),
        )

    def test_listing_context_carries_display_name(self):
        response = self.client.get("/network/up/members/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["network_display_name"],
            "Association of University Presses",
        )
        self.assertContains(response, "Association of University Presses")

    def test_network_without_display_entry_is_rejected(self):
        # NETWORK_DISPLAY_NAMES is the allowlist for path-based network
        # routes too: an undisplayable network must not serve a listing
        response = self.client.get("/network/notanetwork/members/")
        self.assertEqual(response.status_code, 404)


@override_settings(
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
)
class NetworkMembersViewTests(TestCase):
    def setUp(self):
        self.api_member = _make_profile(
            "alice", is_member_of={"STEMED+": True}
        )
        self.api_non_member = _make_profile(
            "bob", is_member_of={"STEMED+": False}
        )
        self.override_member = _make_profile(
            "carol",
            is_member_of={"HASTAC": False},
            role_overrides=["STEMED+"],
        )
        self.override_beats_api = _make_profile(
            "dave",
            is_member_of={"STEMED+": False},
            role_overrides=["STEMED+"],
        )
        self.other_network = _make_profile(
            "erin", is_member_of={"HASTAC": True}
        )
        self.case_variant_override = _make_profile(
            "frank",
            is_member_of={"HASTAC": False},
            role_overrides=["stemed+"],
        )
        self.no_name = _make_profile(
            "ghost", name="", is_member_of={"STEMED+": True}
        )

    def _usernames(self, response):
        return [p.username for p in response.context["profiles"]]

    def test_url_reverses(self):
        self.assertEqual(
            reverse("network_members", kwargs={"network_name": "stemedplus"}),
            "/network/stemedplus/members/",
        )

    def test_lists_only_final_role_members(self):
        response = self.client.get("/network/stemedplus/members/")
        self.assertEqual(response.status_code, 200)
        usernames = self._usernames(response)

        # API-granted and override-granted members are present
        self.assertIn("alice", usernames)
        self.assertIn("carol", usernames)
        self.assertIn("dave", usernames)
        self.assertIn("frank", usernames)

        # API false without override, other networks, and empty-name
        # profiles are excluded
        self.assertNotIn("bob", usernames)
        self.assertNotIn("erin", usernames)
        self.assertNotIn("ghost", usernames)

    def test_override_only_profile_is_listed(self):
        # a profile that has never been synced (is_member_of NULL) but
        # carries a manual override is still a final-role member
        _make_profile(
            "heidi", is_member_of=None, role_overrides=["STEMED+"]
        )
        response = self.client.get("/network/stemedplus/members/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("heidi", self._usernames(response))

    def test_network_slug_is_case_insensitive_in_url(self):
        response = self.client.get("/network/STEMEDPLUS/members/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("alice", self._usernames(response))

    def test_unknown_slug_matches_literal_network_case_insensitively(self):
        _make_profile("grace", is_member_of={"UP": True})
        response = self.client.get("/network/up/members/")
        self.assertEqual(response.status_code, 200)
        usernames = self._usernames(response)
        self.assertEqual(usernames, ["grace"])

    def test_uses_members_template_with_network_context(self):
        response = self.client.get("/network/stemedplus/members/")
        self.assertTemplateUsed(response, "newprofile/members.html")
        self.assertEqual(response.context["network"], "STEMED+")
        self.assertEqual(response.context["total_count"], 4)

    def test_pagination_first_page_caps_at_page_size(self):
        # a dedicated network so setUp fixtures cannot affect the counts
        for i in range(members.PAGE_SIZE + 5):
            _make_profile(
                f"paginetuser{i:03d}", is_member_of={"PAGINET": True}
            )

        response = self.client.get("/network/paginet/members/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["profiles"]), members.PAGE_SIZE
        )
        self.assertTrue(response.context["has_next"])
        self.assertEqual(
            response.context["total_count"], members.PAGE_SIZE + 5
        )

        # follow the next cursor and check the remainder is served
        next_cursor = response.context["next_cursor"]
        response2 = self.client.get(
            f"/network/paginet/members/?cursor={next_cursor}"
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(response2.context["profiles"]), 5)
        self.assertFalse(response2.context["has_next"])
