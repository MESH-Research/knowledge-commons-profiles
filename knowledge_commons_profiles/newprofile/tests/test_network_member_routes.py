"""
Tests for network-prefixed member routes.

Every /members/... route must also be reachable at
/{network}/members/... and dispatch to the *same* view callable with
the *same* kwargs — the network prefix itself is not passed to views
(middleware will later derive the network from the request path).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import Resolver404
from django.urls import resolve
from django.urls import reverse

from knowledge_commons_profiles.newprofile.models import Profile

# (canonical, network-prefixed) pairs covering the full /members/ tree:
# the newprofile profile/edit routes and the cilogon account routes
MIRRORED_ROUTES = [
    # newprofile
    ("/members/", "/stemedplus/members/"),
    ("/members/martin_eve/", "/stemedplus/members/martin_eve/"),
    ("/members/martin_eve/profile/", "/hastac/members/martin_eve/profile/"),
    (
        "/members/martin_eve/profile/public/",
        "/stemedplus/members/martin_eve/profile/public/",
    ),
    ("/members/alice/edit-profile/", "/stemedplus/members/alice/edit-profile/"),
    (
        "/members/alice/edit-profile/upload-avatar/",
        "/stemedplus/members/alice/edit-profile/upload-avatar/",
    ),
    (
        "/members/alice/edit-profile/upload-cover/",
        "/stemedplus/members/alice/edit-profile/upload-cover/",
    ),
    (
        "/members/alice/edit-profile/upload-cv/",
        "/stemedplus/members/alice/edit-profile/upload-cv/",
    ),
    (
        "/members/alice/edit-profile/delete-cv/",
        "/stemedplus/members/alice/edit-profile/delete-cv/",
    ),
    ("/members/alice/profile/edit/", "/stemedplus/members/alice/profile/edit/"),
    (
        "/members/alice/profile/change-avatar/",
        "/stemedplus/members/alice/profile/change-avatar/",
    ),
    (
        "/members/alice/profile/change-cover-image/",
        "/stemedplus/members/alice/profile/change-cover-image/",
    ),
    # cilogon account routes under /members/
    ("/members/alice/settings/", "/stemedplus/members/alice/settings/"),
    (
        "/members/alice/settings/anything/",
        "/stemedplus/members/alice/settings/anything/",
    ),
    (
        "/members/alice/join/stemedplus/",
        "/stemedplus/members/alice/join/stemedplus/",
    ),
    (
        "/members/alice/leave/stemedplus/",
        "/stemedplus/members/alice/leave/stemedplus/",
    ),
    ("/members/alice/roles/", "/stemedplus/members/alice/roles/"),
]


class NetworkPrefixedMemberRouteTests(TestCase):
    def test_prefixed_routes_dispatch_to_same_view_with_same_kwargs(self):
        for canonical, prefixed in MIRRORED_ROUTES:
            with self.subTest(prefixed=prefixed):
                canon = resolve(canonical)
                mirror = resolve(prefixed)
                self.assertIs(mirror.func, canon.func)
                # the network prefix must NOT leak into view kwargs
                self.assertEqual(mirror.kwargs, canon.kwargs)

    def test_unprefixed_reverses_are_unchanged(self):
        # existing reverse()/{% url %} usage must keep producing
        # the canonical /members/ urls
        self.assertEqual(
            reverse("profile", kwargs={"user": "martin_eve"}),
            "/members/martin_eve/",
        )
        self.assertEqual(reverse("members"), "/members/")
        self.assertEqual(
            reverse("manage_roles", kwargs={"user_name": "alice"}),
            "/members/alice/roles/",
        )
        self.assertEqual(
            reverse(
                "self_join_network",
                kwargs={"username": "alice", "network": "hastac"},
            ),
            "/members/alice/join/hastac/",
        )

    def test_bare_network_prefix_is_not_claimed(self):
        # only .../members/... is mirrored; /stemedplus/ alone stays 404
        with self.assertRaises(Resolver404):
            resolve("/stemedplus/")


class NetworkPrefixedMemberRouteEndToEndTests(TestCase):
    """Full request/response through the middleware stack."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass1234"
        )
        Profile.objects.create(
            username="alice", name="Alice", title="Researcher"
        )
        self.client.login(username="alice", password="pass1234")

    def test_network_prefixed_members_listing_renders(self):
        response = self.client.get("/stemedplus/members/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "newprofile/members.html")

    def test_network_prefixed_profile_edit_serves_edit_page(self):
        response = self.client.get(
            "/stemedplus/members/alice/profile/edit/", follow=True
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="name"', content)
        self.assertIn('id="mastodon_edit"', content)
