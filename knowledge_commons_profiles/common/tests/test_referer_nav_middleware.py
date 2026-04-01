import time

from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.common.middleware import RefererNavMiddleware
from knowledge_commons_profiles.newprofile.context_processors import (
    _rewrite_domain,
)
from knowledge_commons_profiles.newprofile.context_processors import nav_links

DOMAIN_MAP = {
    "msucommons-dev.org": "msucommons-dev.org",
    "mla.hcommons-staging.org": "mla.hcommons-staging.org",
}

TEST_NAV_SETTINGS = {
    "NAV_NEWS_FEED_URL": "https://hcommons.org/activity/",
    "NAV_GROUPS_URL": "https://hcommons.org/groups/",
    "NAV_SITES_URL": "https://hcommons.org/sites/",
    "NAV_WORKS_URL": "https://works.hcommons.org/",
    "NAV_SUPPORT_URL": "https://support.hcommons.org/",
    "NAV_ORGANIZATIONS_URL": "https://hcommons.org/societies/",
    "NAV_ABOUT_URL": "https://sustaining.hcommons.org/",
    "NAV_BLOG_URL": "https://team.hcommons.org/",
    "NAV_DEFAULT_DOMAIN": "hcommons.org",
    "NAV_NETWORK_DOMAIN_MAP": DOMAIN_MAP,
    "NAV_NETWORK_SESSION_TIMEOUT": 3600,
}


def _make_get_response():
    def get_response(request):
        from django.http import HttpResponse

        return HttpResponse("ok")

    return get_response


class RefererNavMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, referer=None):
        kwargs = {}
        if referer:
            kwargs["HTTP_REFERER"] = referer
        request = self.factory.get("/", **kwargs)
        request.session = {}
        return request

    @override_settings(**TEST_NAV_SETTINGS)
    def test_no_referer_header_session_unchanged(self):
        request = self._make_request()
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertNotIn("nav_network_domain", request.session)

    @override_settings(**TEST_NAV_SETTINGS)
    def test_unknown_referer_domain_session_unchanged(self):
        request = self._make_request(referer="https://unknown-site.com/page")
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertNotIn("nav_network_domain", request.session)

    @override_settings(**TEST_NAV_SETTINGS)
    def test_exact_domain_match_sets_session(self):
        request = self._make_request(
            referer="https://msucommons-dev.org/some/page"
        )
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertEqual(
            request.session["nav_network_domain"], "msucommons-dev.org"
        )
        self.assertIn("nav_network_domain_ts", request.session)
        self.assertIsInstance(request.session["nav_network_domain_ts"], float)

    @override_settings(**TEST_NAV_SETTINGS)
    def test_subdomain_match_sets_session(self):
        request = self._make_request(
            referer="https://sub.msucommons-dev.org/page"
        )
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertEqual(
            request.session["nav_network_domain"], "msucommons-dev.org"
        )

    @override_settings(**TEST_NAV_SETTINGS)
    def test_new_matching_referer_resets_session(self):
        request = self._make_request(
            referer="https://msucommons-dev.org/page"
        )
        request.session["nav_network_domain"] = "old-domain.org"
        request.session["nav_network_domain_ts"] = 1000.0
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertEqual(
            request.session["nav_network_domain"], "msucommons-dev.org"
        )
        self.assertGreater(
            request.session["nav_network_domain_ts"], 1000.0
        )

    @override_settings(
        **{**TEST_NAV_SETTINGS, "NAV_NETWORK_DOMAIN_MAP": {}}
    )
    def test_empty_domain_map_session_unchanged(self):
        request = self._make_request(
            referer="https://msucommons-dev.org/page"
        )
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertNotIn("nav_network_domain", request.session)

    @override_settings(**TEST_NAV_SETTINGS)
    def test_second_map_entry_matches(self):
        request = self._make_request(
            referer="https://mla.hcommons-staging.org/groups/"
        )
        middleware = RefererNavMiddleware(_make_get_response())
        middleware(request)
        self.assertEqual(
            request.session["nav_network_domain"],
            "mla.hcommons-staging.org",
        )


class RewriteDomainTest(TestCase):
    def test_exact_domain_match_rewrites(self):
        result = _rewrite_domain(
            "https://hcommons.org/groups/",
            "hcommons.org",
            "msucommons-dev.org",
        )
        self.assertEqual(result, "https://msucommons-dev.org/groups/")

    def test_subdomain_url_not_rewritten(self):
        result = _rewrite_domain(
            "https://works.hcommons.org/",
            "hcommons.org",
            "msucommons-dev.org",
        )
        self.assertEqual(result, "https://works.hcommons.org/")

    def test_non_matching_domain_unchanged(self):
        result = _rewrite_domain(
            "https://other-service.com/page",
            "hcommons.org",
            "msucommons-dev.org",
        )
        self.assertEqual(result, "https://other-service.com/page")

    def test_path_preserved(self):
        result = _rewrite_domain(
            "https://hcommons.org/societies/some-society/",
            "hcommons.org",
            "msucommons-dev.org",
        )
        self.assertEqual(
            result, "https://msucommons-dev.org/societies/some-society/"
        )

    def test_port_preserved(self):
        result = _rewrite_domain(
            "https://hcommons.org:8443/groups/",
            "hcommons.org",
            "msucommons-dev.org",
        )
        self.assertEqual(
            result, "https://msucommons-dev.org:8443/groups/"
        )


class NavLinksContextProcessorTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_request(self, session=None):
        request = self.factory.get("/")
        request.session = session if session is not None else {}
        return request

    @override_settings(**TEST_NAV_SETTINGS)
    def test_no_session_key_returns_defaults(self):
        request = self._make_request()
        result = nav_links(request)
        self.assertEqual(result["NAV_GROUPS_URL"], "https://hcommons.org/groups/")
        self.assertEqual(result["NAV_SITES_URL"], "https://hcommons.org/sites/")
        self.assertEqual(result["NAV_WORKS_URL"], "https://works.hcommons.org/")

    @override_settings(**TEST_NAV_SETTINGS)
    def test_valid_session_rewrites_base_domain_urls(self):
        session = {
            "nav_network_domain": "msucommons-dev.org",
            "nav_network_domain_ts": time.time(),
        }
        request = self._make_request(session=session)
        result = nav_links(request)
        self.assertEqual(
            result["NAV_GROUPS_URL"], "https://msucommons-dev.org/groups/"
        )
        self.assertEqual(
            result["NAV_SITES_URL"], "https://msucommons-dev.org/sites/"
        )
        self.assertEqual(
            result["NAV_NEWS_FEED_URL"],
            "https://msucommons-dev.org/activity/",
        )
        self.assertEqual(
            result["NAV_ORGANIZATIONS_URL"],
            "https://msucommons-dev.org/societies/",
        )

    @override_settings(**TEST_NAV_SETTINGS)
    def test_valid_session_does_not_rewrite_subdomain_urls(self):
        session = {
            "nav_network_domain": "msucommons-dev.org",
            "nav_network_domain_ts": time.time(),
        }
        request = self._make_request(session=session)
        result = nav_links(request)
        self.assertEqual(
            result["NAV_WORKS_URL"], "https://works.hcommons.org/"
        )
        self.assertEqual(
            result["NAV_SUPPORT_URL"], "https://support.hcommons.org/"
        )
        self.assertEqual(
            result["NAV_ABOUT_URL"], "https://sustaining.hcommons.org/"
        )
        self.assertEqual(
            result["NAV_BLOG_URL"], "https://team.hcommons.org/"
        )

    @override_settings(**TEST_NAV_SETTINGS)
    def test_expired_session_returns_defaults(self):
        expired_ts = time.time() - 7200  # 2 hours ago
        session = {
            "nav_network_domain": "msucommons-dev.org",
            "nav_network_domain_ts": expired_ts,
        }
        request = self._make_request(session=session)
        result = nav_links(request)
        self.assertEqual(
            result["NAV_GROUPS_URL"], "https://hcommons.org/groups/"
        )

    @override_settings(**TEST_NAV_SETTINGS)
    def test_expired_session_cleans_up_keys(self):
        expired_ts = time.time() - 7200
        session = {
            "nav_network_domain": "msucommons-dev.org",
            "nav_network_domain_ts": expired_ts,
        }
        request = self._make_request(session=session)
        nav_links(request)
        self.assertNotIn("nav_network_domain", request.session)
        self.assertNotIn("nav_network_domain_ts", request.session)
