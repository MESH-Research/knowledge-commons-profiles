"""
Tests for NetworkSubdomainMiddleware.

Requests arriving on a network subdomain (stemedplus.profile.example)
carry the canonical network on the request, and /members/ renders the
network-scoped listing for that network. Requests on a base domain are
unannotated and the directory is unscoped.
"""

import json

from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.common.middleware import (
    NetworkSubdomainMiddleware,
)
from knowledge_commons_profiles.newprofile.models import Profile

SOCIETY_MAPPINGS = {"stemedplus": "STEMED+", "hastac": "HASTAC"}
BASE_DOMAINS = [
    "profile.hcommons-dev.org",
    "profile.hcommons.org",
    "localhost",
]


@override_settings(
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS=SOCIETY_MAPPINGS,
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

    def test_unknown_subdomain_is_treated_as_literal_network(self):
        request = self._request_for("up.profile.hcommons.org")
        self.assertEqual(request.network, "up")
        self.assertEqual(request.network_slug, "up")

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
