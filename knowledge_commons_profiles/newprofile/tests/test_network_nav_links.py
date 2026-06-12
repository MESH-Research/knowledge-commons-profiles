"""
Tests for network-aware navbar links.

On a network host (up.profile.hcommons.org) or network path prefix,
the community links (news feed/activity, groups, sites) point at the
network's own Commons domain (up.hcommons.org). Works, Help & Support,
KC Organizations, About and the Team Blog never follow the network —
including KC Organizations, which lives on the default domain and must
be excluded by key, not by hostname.
"""

import json
import time

from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.context_processors import nav_links
from knowledge_commons_profiles.newprofile.models import Profile

NAV_SETTINGS = {
    "NAV_NEWS_FEED_URL": "https://hcommons.org/activity/",
    "NAV_GROUPS_URL": "https://hcommons.org/groups/",
    "NAV_SITES_URL": "https://hcommons.org/sites/",
    "NAV_WORKS_URL": "https://works.hcommons.org/",
    "NAV_SUPPORT_URL": "https://support.hcommons.org/",
    "NAV_ORGANIZATIONS_URL": "https://hcommons.org/societies/",
    "NAV_ABOUT_URL": "https://sustaining.hcommons.org/",
    "NAV_BLOG_URL": "https://team.hcommons.org/",
    "NAV_DEFAULT_DOMAIN": "hcommons.org",
}


@override_settings(**NAV_SETTINGS)
class NetworkAwareNavLinksTests(TestCase):
    def _nav_for_network(self, slug, session=None):
        request = RequestFactory().get("/members/")
        request.network_slug = slug
        request.network = slug
        request.session = session if session is not None else {}
        return nav_links(request)

    def test_community_links_follow_the_network(self):
        urls = self._nav_for_network("up")
        self.assertEqual(
            urls["NAV_NEWS_FEED_URL"], "https://up.hcommons.org/activity/"
        )
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://up.hcommons.org/groups/"
        )
        self.assertEqual(
            urls["NAV_SITES_URL"], "https://up.hcommons.org/sites/"
        )

    def test_fixed_links_never_follow_the_network(self):
        urls = self._nav_for_network("stemedplus")
        self.assertEqual(
            urls["NAV_WORKS_URL"], "https://works.hcommons.org/"
        )
        self.assertEqual(
            urls["NAV_SUPPORT_URL"], "https://support.hcommons.org/"
        )
        # KC Organizations lives ON the default domain and must still
        # not follow the network
        self.assertEqual(
            urls["NAV_ORGANIZATIONS_URL"], "https://hcommons.org/societies/"
        )
        self.assertEqual(
            urls["NAV_ABOUT_URL"], "https://sustaining.hcommons.org/"
        )
        self.assertEqual(urls["NAV_BLOG_URL"], "https://team.hcommons.org/")

    def test_no_network_leaves_links_unchanged(self):
        urls = self._nav_for_network(None)
        self.assertEqual(
            urls["NAV_NEWS_FEED_URL"], "https://hcommons.org/activity/"
        )
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://hcommons.org/groups/"
        )

    def test_network_beats_referer_session_domain(self):
        session = {
            "nav_network_domain": "msu.edu",
            "nav_network_domain_ts": time.time(),
        }
        urls = self._nav_for_network("up", session=session)
        self.assertEqual(
            urls["NAV_NEWS_FEED_URL"], "https://up.hcommons.org/activity/"
        )


DOMAIN_OVERRIDES = {
    "msu": {
        "dev": "msucommons-dev.org",
        "main": "commons.msu.edu",
    },
}


@override_settings(**NAV_SETTINGS, NETWORK_DOMAIN_OVERRIDES=DOMAIN_OVERRIDES)
class NetworkDomainOverrideTests(TestCase):
    def _nav_for_network(self, slug):
        request = RequestFactory().get("/members/")
        request.network_slug = slug
        request.network = slug
        request.session = {}
        return nav_links(request)

    @override_settings(NETWORK_DOMAIN_ENVIRONMENT="dev")
    def test_overridden_network_uses_environment_domain_on_dev(self):
        urls = self._nav_for_network("msu")
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://msucommons-dev.org/groups/"
        )
        self.assertEqual(
            urls["NAV_NEWS_FEED_URL"],
            "https://msucommons-dev.org/activity/",
        )
        self.assertEqual(
            urls["NAV_SITES_URL"], "https://msucommons-dev.org/sites/"
        )

    @override_settings(NETWORK_DOMAIN_ENVIRONMENT="main")
    def test_overridden_network_uses_environment_domain_on_main(self):
        urls = self._nav_for_network("msu")
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://commons.msu.edu/groups/"
        )

    @override_settings(NETWORK_DOMAIN_ENVIRONMENT="dev")
    def test_works_link_ignores_domain_overrides(self):
        urls = self._nav_for_network("msu")
        self.assertEqual(
            urls["NAV_WORKS_URL"], "https://works.hcommons.org/"
        )

    @override_settings(NETWORK_DOMAIN_ENVIRONMENT="dev")
    def test_network_without_override_uses_subdomain_of_default(self):
        urls = self._nav_for_network("up")
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://up.hcommons.org/groups/"
        )

    @override_settings(NETWORK_DOMAIN_ENVIRONMENT="test")
    def test_override_without_environment_entry_falls_back(self):
        # msu has dev/main entries but nothing for this environment
        urls = self._nav_for_network("msu")
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://msu.hcommons.org/groups/"
        )


@override_settings(
    **NAV_SETTINGS,
    ALLOWED_HOSTS=["*"],
    KNOWN_SOCIETY_MAPPINGS={"stemedplus": "STEMED+"},
    NETWORK_DISPLAY_NAMES={
        "up": "Association of University Presses",
        "stemed+": "STEM Ed+",
    },
    NETWORK_SUBDOMAIN_BASE_DOMAINS=["profile.hcommons-dev.org"],
    NETWORK_SUBDOMAIN_IGNORED=["www"],
)
class NetworkNavRenderingTests(TestCase):
    def setUp(self):
        Profile.objects.create(
            username="alice",
            name="Alice",
            is_member_of=json.dumps({"UP": True}),
        )

    def test_subdomain_page_renders_network_nav_links(self):
        response = self.client.get(
            "/members/", headers={"host": "up.profile.hcommons-dev.org"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://up.hcommons.org/activity/")
        self.assertContains(response, "https://up.hcommons.org/groups/")
        self.assertContains(response, "https://works.hcommons.org/")
        self.assertContains(response, "https://hcommons.org/societies/")


@override_settings(**NAV_SETTINGS)
class RefererSessionIgnoredTests(TestCase):
    """The referer-derived session domain no longer drives nav links.

    Network nav domains come only from the subdomain or network path
    prefix; on the bare profile domain the links must stay on the
    environment's own domains even when an old session value is
    present (previously this rewrote every community link, so e.g.
    a visit from an MSU page pinned the whole nav to MSU for an hour).
    """

    def test_session_domain_does_not_rewrite_links_without_network(self):
        request = RequestFactory().get("/members/airminded/")
        request.network_slug = None
        request.network = None
        request.session = {
            "nav_network_domain": "msucommons-dev.org",
            "nav_network_domain_ts": time.time(),
        }
        urls = nav_links(request)
        self.assertEqual(
            urls["NAV_NEWS_FEED_URL"], "https://hcommons.org/activity/"
        )
        self.assertEqual(
            urls["NAV_GROUPS_URL"], "https://hcommons.org/groups/"
        )
        self.assertEqual(
            urls["NAV_SITES_URL"], "https://hcommons.org/sites/"
        )
