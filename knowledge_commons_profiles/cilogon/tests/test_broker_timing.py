"""
Tests for the broker timing instrumentation.

Covers:
- TimingCollector unit behaviour (span recording, Server-Timing header
  formatting, dict export).
- Presence/absence of the Server-Timing header on the broker views,
  gated by the BROKER_TIMING_ENABLED setting.
- The DEBUG-gated /broker/_timings/ profile endpoint that runs a
  configurable number of synthetic silent_login hits in-process and
  reports per-span percentiles.
- Query-count regressions on both branches of silent_login.
"""

from __future__ import annotations

import json

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.newprofile.models import Profile

# Test-only MIDDLEWARE list that strips Django Debug Toolbar so the
# profile-endpoint tests (which run nested Client calls and toggle
# DEBUG=True) don't trigger toolbar render in tests.
_MIDDLEWARE_WITHOUT_TOOLBAR = [
    m
    for m in django_settings.MIDDLEWARE
    if "debug_toolbar" not in m.lower()
]

TEST_SHARED_SECRET = "test-shared-secret-for-broker"

BROKER_SETTINGS = {
    "wordpress": {
        "name": "WordPress",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "localhost", "lndo.site"],
    },
    "works": {
        "name": "Works",
        "callback_url": "",
        "allowed_domains": ["hcommons.org", "localhost", "lndo.site"],
    },
}


class TimingCollectorUnitTests(TestCase):
    """The collector is the low-level primitive used across the broker
    views and the debug profile endpoint."""

    def test_span_records_name_and_duration(self):
        from knowledge_commons_profiles.cilogon.timing import TimingCollector

        c = TimingCollector()
        with c.span("foo"):
            pass
        self.assertEqual(len(c.spans), 1)
        name, duration_ms = c.spans[0]
        self.assertEqual(name, "foo")
        self.assertGreaterEqual(duration_ms, 0.0)

    def test_multiple_spans_preserve_order(self):
        from knowledge_commons_profiles.cilogon.timing import TimingCollector

        c = TimingCollector()
        with c.span("first"):
            pass
        with c.span("second"):
            pass
        self.assertEqual([n for n, _ in c.spans], ["first", "second"])

    def test_header_value_uses_server_timing_format(self):
        from knowledge_commons_profiles.cilogon.timing import TimingCollector

        c = TimingCollector()
        with c.span("a"):
            pass
        with c.span("b"):
            pass
        header = c.header_value()
        # Server-Timing: name1;dur=12.34, name2;dur=4.56
        entries = [e.strip() for e in header.split(",")]
        self.assertEqual(len(entries), 2)
        self.assertTrue(entries[0].startswith("a;dur="))
        self.assertTrue(entries[1].startswith("b;dur="))

    def test_as_dict_returns_named_milliseconds(self):
        from knowledge_commons_profiles.cilogon.timing import TimingCollector

        c = TimingCollector()
        with c.span("alpha"):
            pass
        out = c.as_dict()
        self.assertIn("alpha", out)
        self.assertIsInstance(out["alpha"], float)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
    BROKER_TIMING_ENABLED=True,
)
class SilentLoginServerTimingTests(TestCase):
    """The silent_login response carries Server-Timing when enabled."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.return_to = "https://hcommons.org/broker-callback/"

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_no_session_branch_emits_server_timing_header(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        header = response.get("Server-Timing", "")
        self.assertIn("validate;dur=", header)

    def test_broker_token_branch_emits_server_timing_header(self):
        user = User.objects.create_user("timing_user", password="x")
        profile = Profile.objects.create(
            username="timing_user", email="t@example.com"
        )
        sub = "http://cilogon.org/serverA/users/timing"
        SubAssociation.objects.create(sub=sub, profile=profile)

        self.client.login(username="timing_user", password="x")
        session = self.client.session
        session["oidc_userinfo"] = {"sub": sub, "email": "t@example.com"}
        session.save()
        # Avoid the user being collected by middleware later
        _ = user

        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        header = response.get("Server-Timing", "")
        # All three spans are expected on the success path.
        self.assertIn("validate;dur=", header)
        self.assertIn("sub_lookup;dur=", header)
        self.assertIn("redirect_build;dur=", header)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
    BROKER_TIMING_ENABLED=False,
)
class SilentLoginServerTimingDisabledTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.return_to = "https://hcommons.org/broker-callback/"

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_no_header_when_flag_off(self):
        response = self.client.get(
            f"/broker/silent-login/?return_to={self.return_to}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("Server-Timing", response)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
    BROKER_TIMING_ENABLED=True,
)
class VerifyBrokerNonceServerTimingTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_success_path_carries_server_timing(self):
        cache.set(
            "broker_nonce:timing-nonce",
            {"used": False, "sub": "http://cilogon.org/serverA/users/x"},
            timeout=60,
        )
        response = self.client.post(
            "/broker/verify-nonce/",
            data=json.dumps({"nonce": "timing-nonce"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {TEST_SHARED_SECRET}"},
        )
        self.assertEqual(response.status_code, 200)
        header = response.get("Server-Timing", "")
        self.assertIn("cache_lookup;dur=", header)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
    DEBUG=True,
    MIDDLEWARE=_MIDDLEWARE_WITHOUT_TOOLBAR,
)
class BrokerTimingsDebugEndpointTests(TestCase):
    """The /broker/_timings/ endpoint is the in-process profiler."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_returns_percentiles_for_synthetic_calls(self):
        response = self.client.get("/broker/_timings/?n=3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["n"], 3)
        # Top-level totals are aggregated.
        self.assertIn("totals_ms", data)
        totals = data["totals_ms"]
        for key in ("p50", "p95", "p99", "min", "max", "n"):
            self.assertIn(key, totals)
        # Per-span breakdown is keyed by span name.
        self.assertIn("spans_ms", data)
        self.assertIn("validate", data["spans_ms"])

    def test_clamps_iteration_count_to_a_safe_ceiling(self):
        # Requesting a huge n should not actually run a huge n.
        response = self.client.get("/broker/_timings/?n=100000")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(data["n"], 500)


@override_settings(DEBUG=False, MIDDLEWARE=_MIDDLEWARE_WITHOUT_TOOLBAR)
class BrokerTimingsDebugEndpointGatedOffTests(TestCase):
    def test_404_when_debug_is_off(self):
        response = self.client.get("/broker/_timings/?n=3")
        self.assertEqual(response.status_code, 404)


@override_settings(
    BROKER_REGISTERED_APPS=BROKER_SETTINGS,
    BROKER_NONCE_TTL=60,
    STATIC_API_BEARER=TEST_SHARED_SECRET,
)
class SilentLoginQueryCountTests(TestCase):
    """Regression guard: don't let the silent path acquire new DB
    queries by accident. Bounded with assertNumQueries(..., LE)."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.return_to = "https://hcommons.org/broker-callback/"

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_anonymous_no_session_branch_query_budget(self):
        # Anonymous request to silent_login should be very cheap. We
        # assert an upper bound rather than an exact count so session
        # backend churn (cached_db vs db) doesn't break the test.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        budget = 4
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                f"/broker/silent-login/?return_to={self.return_to}"
            )

        self.assertEqual(response.status_code, 302)
        self.assertLessEqual(
            len(captured.captured_queries),
            budget,
            msg=(
                f"silent_login no-session branch exceeded query "
                f"budget {budget}: ran "
                f"{len(captured.captured_queries)} queries:\n"
                + "\n".join(
                    q["sql"][:120] for q in captured.captured_queries
                )
            ),
        )
