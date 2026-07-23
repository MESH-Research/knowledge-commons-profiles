"""
Tests for NetworkSubdomainMiddleware.

Requests arriving on a network subdomain (stemedplus.profile.example)
carry the canonical network on the request, and /members/ renders the
network-scoped listing for that network. Requests on a base domain are
unannotated and the directory is unscoped.
"""

import json

from django.http import Http404
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.common.middleware import (
    NetworkSubdomainMiddleware,
)
from knowledge_commons_profiles.newprofile.models import Profile

SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}
DISPLAY_NAMES = {
    "stemed+": "STEM Ed+",
    "hastac": "HASTAC",
    "up": "Association of University Presses",
}
BASE_DOMAINS = [
    "profile.hcommons-dev.org",
    "profile.hcommons.org",
    "localhost",
]


@override_settings(
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    NETWORK_SUBDOMAIN_BASE_DOMAINS=BASE_DOMAINS,
    NETWORK_SUBDOMAIN_IGNORED=["www"],
)
class NetworkSubdomainMiddlewareTests(TestCase):
    def _request_for(self, host):
        request = RequestFactory().get("/", HTTP_HOST=host)
        NetworkSubdomainMiddleware(lambda r: r)(request)
        return request

    def test_known_network_subdomain_sets_canonical_network(self):
        request = self._request_for("stemedplus.profile.hcommons-dev.org")
        self.assertEqual(request.network, "STEMED+")
        self.assertEqual(request.network_slug, "stemedplus")

    def test_subdomain_detection_is_case_insensitive(self):
        request = self._request_for("STEMEDPLUS.profile.hcommons-dev.org")
        self.assertEqual(request.network, "STEMED+")
        self.assertEqual(request.network_slug, "stemedplus")

    def test_literal_subdomain_in_display_list_is_allowed(self):
        # "up" has no KNOWN_SOCIETY_MAPPINGS entry but is a displayable
        # network, so the subdomain is valid with its literal name
        request = self._request_for("up.profile.hcommons.org")
        self.assertEqual(request.network, "up")
        self.assertEqual(request.network_slug, "up")

    def test_unknown_subdomain_is_rejected(self):
        # subdomains outside NETWORK_DISPLAY_NAMES must not fall
        # through as phantom networks
        with self.assertRaises(Http404):
            self._request_for("notanetwork.profile.hcommons.org")

    def test_unknown_subdomain_rejection_is_case_insensitive(self):
        with self.assertRaises(Http404):
            self._request_for("NOTANETWORK.profile.hcommons.org")

    def test_base_domain_carries_no_network(self):
        request = self._request_for("profile.hcommons-dev.org")
        self.assertIsNone(request.network)
        self.assertIsNone(request.network_slug)

    def test_www_subdomain_is_not_a_network(self):
        request = self._request_for("www.profile.hcommons.org")
        self.assertIsNone(request.network)

    def test_unrelated_host_carries_no_network(self):
        request = self._request_for("testserver")
        self.assertIsNone(request.network)

    def test_port_is_ignored(self):
        request = self._request_for(
            "stemedplus.profile.hcommons-dev.org:8443"
        )
        self.assertEqual(request.network, "STEMED+")

    def test_nested_subdomains_are_not_networks(self):
        request = self._request_for("foo.bar.profile.hcommons.org")
        self.assertIsNone(request.network)

    def test_localhost_subdomain_works_for_local_dev(self):
        request = self._request_for("stemedplus.localhost")
        self.assertEqual(request.network, "STEMED+")


@override_settings(
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    NETWORK_SUBDOMAIN_BASE_DOMAINS=BASE_DOMAINS,
    NETWORK_SUBDOMAIN_IGNORED=["www"],
)
class MembersListingOnSubdomainTests(TestCase):
    def setUp(self):
        Profile.objects.create(
            username="alice",
            name="Alice",
            is_member_of=json.dumps({"STEMED+": True}),
        )
        Profile.objects.create(
            username="bob",
            name="Bob",
            is_member_of=json.dumps({"STEMED+": False}),
        )

    def test_members_listing_is_network_scoped_on_subdomain(self):
        response = self.client.get(
            "/members/",
            headers={"host": "stemedplus.profile.hcommons-dev.org"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["network"], "STEMED+")
        usernames = [p.username for p in response.context["profiles"]]
        self.assertEqual(usernames, ["alice"])

    def test_members_listing_is_unscoped_on_base_domain(self):
        response = self.client.get(
            "/members/", headers={"host": "profile.hcommons-dev.org"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("network"))
        usernames = [p.username for p in response.context["profiles"]]
        self.assertEqual(usernames, ["alice", "bob"])

    def test_other_member_routes_still_resolve_on_subdomain(self):
        # the subdomain must not break non-listing member pages
        response = self.client.get(
            "/members/alice/",
            headers={"host": "stemedplus.profile.hcommons-dev.org"}
        )
        self.assertNotEqual(response.status_code, 404)

    def test_unknown_subdomain_returns_404_for_every_path(self):
        for path in ("/members/", "/members/alice/", "/"):
            response = self.client.get(
                path,
                headers={"host": "notanetwork.profile.hcommons-dev.org"},
            )
            self.assertEqual(
                response.status_code, 404, f"expected 404 for {path}"
            )


@override_settings(
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    NETWORK_SUBDOMAIN_BASE_DOMAINS=BASE_DOMAINS,
    NETWORK_SUBDOMAIN_IGNORED=["www"],
)
class PathPrefixNetworkEnforcementTests(TestCase):
    """The display-name allowlist gates path-based network routes too."""

    def setUp(self):
        Profile.objects.create(
            username="alice",
            name="Alice",
            is_member_of=json.dumps({"STEMED+": True}),
        )
        Profile.objects.create(
            username="bob",
            name="Bob",
            is_member_of=json.dumps({"STEMED+": False}),
        )

    def test_unknown_path_prefix_is_rejected(self):
        for path in (
            "/notanetwork/members/",
            "/notanetwork/members/alice/",
        ):
            response = self.client.get(path)
            self.assertEqual(
                response.status_code, 404, f"expected 404 for {path}"
            )

    def test_known_path_prefix_scopes_the_listing(self):
        # /stemedplus/members/ behaves like the subdomain listing:
        # network detected from the path, directory scoped
        response = self.client.get("/stemedplus/members/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["network"], "STEMED+")
        usernames = [p.username for p in response.context["profiles"]]
        self.assertEqual(usernames, ["alice"])

    def test_member_pages_on_known_prefix_still_serve(self):
        response = self.client.get("/stemedplus/members/alice/")
        self.assertNotEqual(response.status_code, 404)

    def test_canonical_members_routes_are_unaffected(self):
        response = self.client.get("/members/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("network"))
        usernames = [p.username for p in response.context["profiles"]]
        self.assertEqual(usernames, ["alice", "bob"])

    def test_member_profile_named_members_is_not_a_network_path(self):
        # /members/members/ is the profile page of a user called
        # "members", not a network prefix; it must not be rejected by
        # the allowlist
        Profile.objects.create(username="members", name="Members User")
        response = self.client.get("/members/members/")
        self.assertNotEqual(response.status_code, 404)


@override_settings(
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
    NETWORK_DISPLAY_NAMES=DISPLAY_NAMES,
    NETWORK_SUBDOMAIN_BASE_DOMAINS=BASE_DOMAINS,
    NETWORK_SUBDOMAIN_IGNORED=["www"],
    NETWORK_HOST_ALIASES={"profile.stemedplus.org": "stemedplus"},
)
class NetworkHostAliasTests(TestCase):
    """A dedicated per-network host (its own registrable domain) is
    annotated with its network exactly like a <slug>.<base> subdomain."""

    def _request_for(self, host):
        request = RequestFactory().get("/", HTTP_HOST=host)
        NetworkSubdomainMiddleware(lambda r: r)(request)
        return request

    def test_alias_host_sets_canonical_network(self):
        request = self._request_for("profile.stemedplus.org")
        self.assertEqual(request.network, "STEMED+")
        self.assertEqual(request.network_slug, "stemedplus")

    def test_alias_host_is_case_insensitive(self):
        request = self._request_for("PROFILE.STEMEDPLUS.ORG")
        self.assertEqual(request.network, "STEMED+")
        self.assertEqual(request.network_slug, "stemedplus")

    def test_alias_host_ignores_port(self):
        request = self._request_for("profile.stemedplus.org:443")
        self.assertEqual(request.network, "STEMED+")

    def test_non_alias_host_on_same_domain_carries_no_network(self):
        # only the exact configured host is an alias; the apex and other
        # subdomains of the same registrable domain are not networks here
        self.assertIsNone(self._request_for("stemedplus.org").network)
        self.assertIsNone(self._request_for("www.stemedplus.org").network)

    def test_existing_base_domain_parsing_still_works(self):
        request = self._request_for("stemedplus.profile.hcommons.org")
        self.assertEqual(request.network, "STEMED+")
        self.assertEqual(request.network_slug, "stemedplus")
