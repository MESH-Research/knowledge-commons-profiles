# tests for the member search box on network-scoped listings
import json

from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import Profile

SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}
DISPLAY_NAMES = {
    "stemed+": "STEM Ed+",
    "hastac": "HASTAC",
}


def _make_profile(username, name=None, is_member_of=None):
    return Profile.objects.create(
        username=username,
        name=name if name is not None else username.title(),
        is_member_of=json.dumps(is_member_of) if is_member_of else None,
        role_overrides=[],
    )


@override_settings(
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
)
class NetworkMembersSearchTests(TestCase):
    """POSTing the search form on a network listing filters the roster."""

    def setUp(self):
        self.alice = _make_profile(
            "alice", name="Alice Smith", is_member_of={"STEMED+": True}
        )
        self.bob = _make_profile(
            "bob", name="Bob Jones", is_member_of={"STEMED+": True}
        )
        # matches "ali" searches but belongs to a different network
        self.alister = _make_profile(
            "alister", name="Alister Other", is_member_of={"HASTAC": True}
        )

    def _usernames(self, response):
        return [p.username for p in response.context["profiles"]]

    def test_search_filters_by_username(self):
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "ali"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["alice"])

    def test_search_filters_by_display_name(self):
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "Jones"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["bob"])

    def test_search_stays_scoped_to_the_network(self):
        # "alister" matches the term but is not a STEMED+ member
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "ali"}
        )
        self.assertNotIn("alister", self._usernames(response))

    def test_search_with_no_matches_returns_empty_not_full_list(self):
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "zzznomatch"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), [])
        self.assertEqual(response.context["total_count"], 0)

    def test_search_total_count_reflects_filtered_results(self):
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "ali"}
        )
        self.assertEqual(response.context["total_count"], 1)

    def test_blank_search_returns_full_network_list(self):
        response = self.client.post(
            "/network/stemedplus/members/", {"username": "   "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["alice", "bob"])

    def test_get_still_returns_full_network_list(self):
        response = self.client.get("/network/stemedplus/members/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["alice", "bob"])


@override_settings(
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    ALLOWED_HOSTS=["*"],
    NETWORK_SUBDOMAIN_BASE_DOMAINS=["profile.hcommons-dev.org"],
    NETWORK_SUBDOMAIN_IGNORED=["www"],
    NETWORK_HOST_ALIASES={"profile.stemedplus.org": "stemedplus"},
)
class SubdomainMembersSearchTests(TestCase):
    """The same search must work when the network arrives via the host."""

    def setUp(self):
        _make_profile(
            "alice", name="Alice Smith", is_member_of={"STEMED+": True}
        )
        _make_profile("bob", name="Bob Jones", is_member_of={"STEMED+": True})

    def _usernames(self, response):
        return [p.username for p in response.context["profiles"]]

    def test_search_on_network_subdomain_filters_results(self):
        response = self.client.post(
            "/members/",
            {"username": "ali"},
            headers={"host": "stemedplus.profile.hcommons-dev.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["alice"])

    def test_search_on_aliased_external_domain_filters_results(self):
        response = self.client.post(
            "/members/",
            {"username": "ali"},
            headers={"host": "profile.stemedplus.org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), ["alice"])

    def test_subdomain_search_remains_network_scoped(self):
        _make_profile(
            "alister", name="Alister Other", is_member_of={"HASTAC": True}
        )
        response = self.client.post(
            "/members/",
            {"username": "ali"},
            headers={"host": "stemedplus.profile.hcommons-dev.org"},
        )
        self.assertEqual(self._usernames(response), ["alice"])
