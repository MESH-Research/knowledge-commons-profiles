"""
Tests for CILogon login forwarding on network subdomains.

A network subdomain (e.g. up.profile.hcommons.org) is not a registered
CILogon redirect_uri, so its /login/ must send CILogon the base/registered
domain's callback and pack its own callback into the OIDC state, so the
registered domain forwards the code back. This reuses the existing
domain-proxy state-forwarding mechanism, generalised for subdomains.
"""

import base64
import json
from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.cilogon import oauth
from knowledge_commons_profiles.cilogon.views import cilogon_login

BASE_DOMAINS = ["profile.hcommons.org", "profile.hcommons-dev.org"]

# prod-like: no domain proxy
PROD = {
    "OIDC_CALLBACK": "cilogon/callback/",
    "CILOGON_REGISTERED_DOMAIN": "profile.hcommons.org",
    "CILOGON_ACTUAL_DOMAIN": "",
    "NETWORK_SUBDOMAIN_BASE_DOMAINS": BASE_DOMAINS,
    "NETWORK_SUBDOMAIN_IGNORED": ["www"],
}

# dev-like: shares the prod client via the domain proxy
DEV = {
    "OIDC_CALLBACK": "cilogon/callback/",
    "CILOGON_REGISTERED_DOMAIN": "profile.hcommons.org",
    "CILOGON_ACTUAL_DOMAIN": "profile.hcommons-dev.org",
    "NETWORK_SUBDOMAIN_BASE_DOMAINS": BASE_DOMAINS,
    "NETWORK_SUBDOMAIN_IGNORED": ["www"],
}


def _next_url_in_state(state: str):
    return json.loads(base64.urlsafe_b64decode(state).decode())["callback_next"]


class NetworkBaseDomainTests(TestCase):
    @override_settings(**PROD)
    def test_subdomain_returns_base(self):
        self.assertEqual(
            oauth.network_base_domain("up.profile.hcommons.org"),
            "profile.hcommons.org",
        )

    @override_settings(**PROD)
    def test_base_domain_itself_returns_none(self):
        self.assertIsNone(oauth.network_base_domain("profile.hcommons.org"))

    @override_settings(**PROD)
    def test_ignored_subdomain_returns_none(self):
        self.assertIsNone(
            oauth.network_base_domain("www.profile.hcommons.org")
        )

    @override_settings(**PROD)
    def test_nested_subdomain_returns_none(self):
        self.assertIsNone(
            oauth.network_base_domain("a.b.profile.hcommons.org")
        )

    @override_settings(**PROD)
    def test_unrelated_host_returns_none(self):
        self.assertIsNone(oauth.network_base_domain("works.hcommons.org"))

    @override_settings(**PROD)
    def test_port_is_ignored(self):
        self.assertEqual(
            oauth.network_base_domain("up.profile.hcommons.org:8443"),
            "profile.hcommons.org",
        )


class RedirectUriOnSubdomainTests(TestCase):
    def _request(self, host):
        return RequestFactory().get("/login/", headers={"host": host})

    @override_settings(**PROD)
    def test_prod_subdomain_uses_base_callback(self):
        uri = oauth.get_oauth_redirect_uri(
            self._request("up.profile.hcommons.org")
        )
        self.assertEqual(uri, "https://profile.hcommons.org/cilogon/callback/")

    @override_settings(**PROD)
    def test_prod_apex_unchanged(self):
        uri = oauth.get_oauth_redirect_uri(
            self._request("profile.hcommons.org")
        )
        self.assertEqual(uri, "https://profile.hcommons.org/cilogon/callback/")

    @override_settings(**DEV)
    def test_dev_subdomain_chains_to_registered(self):
        # subdomain -> base (profile.hcommons-dev.org) -> registered
        uri = oauth.get_oauth_redirect_uri(
            self._request("stemedplus.profile.hcommons-dev.org")
        )
        self.assertEqual(uri, "https://profile.hcommons.org/cilogon/callback/")

    @override_settings(**DEV)
    def test_dev_apex_proxy_behaviour_preserved(self):
        uri = oauth.get_oauth_redirect_uri(
            self._request("profile.hcommons-dev.org")
        )
        self.assertEqual(uri, "https://profile.hcommons.org/cilogon/callback/")


class ForwardingStateOnSubdomainTests(TestCase):
    def _request(self, host):
        return RequestFactory().get("/login/", headers={"host": host})

    @override_settings(**PROD)
    def test_subdomain_packs_its_own_callback(self):
        state = oauth.get_forwarding_state_for_proxy(
            self._request("up.profile.hcommons.org")
        )
        self.assertEqual(
            _next_url_in_state(state),
            "https://up.profile.hcommons.org/cilogon/callback/",
        )

    @override_settings(**PROD)
    def test_prod_apex_packs_empty(self):
        state = oauth.get_forwarding_state_for_proxy(
            self._request("profile.hcommons.org")
        )
        self.assertEqual(_next_url_in_state(state), "")

    @override_settings(**DEV)
    def test_dev_apex_proxy_packs_actual_domain(self):
        # existing domain-proxy behaviour preserved on the dev apex
        state = oauth.get_forwarding_state_for_proxy(
            self._request("profile.hcommons-dev.org")
        )
        self.assertEqual(
            _next_url_in_state(state),
            "https://profile.hcommons-dev.org/cilogon/callback/",
        )

    @override_settings(**DEV)
    def test_dev_subdomain_packs_subdomain_not_base(self):
        state = oauth.get_forwarding_state_for_proxy(
            self._request("stemedplus.profile.hcommons-dev.org")
        )
        self.assertEqual(
            _next_url_in_state(state),
            "https://stemedplus.profile.hcommons-dev.org/cilogon/callback/",
        )


class ForwardTargetTests(TestCase):
    """is_request_from_actual_domain decides whether to process or forward."""

    def _callback_request(self, host, next_url):
        state = oauth.pack_state(next_url) if next_url is not None else None
        params = {"code": "abc"}
        if state is not None:
            params["state"] = state
        return RequestFactory().get(
            "/cilogon/callback/", params, headers={"host": host}
        )

    @override_settings(**PROD)
    def test_subdomain_is_its_own_forward_target(self):
        # arrived at the subdomain encoded in state -> process here
        req = self._callback_request(
            "up.profile.hcommons.org",
            "https://up.profile.hcommons.org/cilogon/callback/",
        )
        self.assertTrue(oauth.is_request_from_actual_domain(req))

    @override_settings(**PROD)
    def test_registered_domain_forwards_to_subdomain(self):
        # on the registered domain with a subdomain target -> not the
        # target, so the callback forwards
        req = self._callback_request(
            "profile.hcommons.org",
            "https://up.profile.hcommons.org/cilogon/callback/",
        )
        self.assertFalse(oauth.is_request_from_actual_domain(req))

    @override_settings(**DEV)
    def test_static_proxy_actual_domain_still_processes(self):
        # regression: the dev apex (actual domain) is still recognised as
        # the forward target
        req = self._callback_request(
            "profile.hcommons-dev.org",
            "https://profile.hcommons-dev.org/cilogon/callback/",
        )
        self.assertTrue(oauth.is_request_from_actual_domain(req))

    @override_settings(**PROD)
    def test_forged_non_network_host_is_not_a_forward_target(self):
        # the state's next_url is attacker-forgeable: a host that is not a
        # recognised network subdomain (nor the proxy actual domain) must
        # not be treated as a local forward target, even if it matches the
        # request host
        req = self._callback_request(
            "evil.example.com",
            "https://evil.example.com/cilogon/callback/",
        )
        self.assertFalse(oauth.is_request_from_actual_domain(req))

    @override_settings(**PROD)
    def test_no_state_is_not_a_forward_target(self):
        req = self._callback_request("profile.hcommons.org", None)
        self.assertFalse(oauth.is_request_from_actual_domain(req))


@override_settings(**PROD)
class CilogonLoginIntegrationTests(TestCase):
    """End-to-end wiring through the real cilogon_login view."""

    def _request(self, host):
        request = RequestFactory().get("/login/", headers={"host": host})
        request.user = AnonymousUser()
        SessionMiddleware(get_response=MagicMock()).process_request(request)
        request.session.save()
        return request

    def _login_authorize_args(self, host):
        request = self._request(host)
        with (
            patch("knowledge_commons_profiles.cilogon.views.app_logout"),
            patch(
                "knowledge_commons_profiles.cilogon.views."
                "oauth.cilogon.authorize_redirect",
                return_value=MagicMock(status_code=302),
            ) as authorize,
        ):
            cilogon_login(request)
        return authorize.call_args

    def test_subdomain_login_sends_registered_uri_and_subdomain_state(self):
        args = self._login_authorize_args("up.profile.hcommons.org")
        # redirect_uri is the registered base callback
        self.assertEqual(
            args.args[1], "https://profile.hcommons.org/cilogon/callback/"
        )
        # state packs the subdomain's own callback for forward-back
        self.assertEqual(
            _next_url_in_state(args.kwargs["state"]),
            "https://up.profile.hcommons.org/cilogon/callback/",
        )

    def test_apex_login_sends_registered_uri_and_empty_state(self):
        args = self._login_authorize_args("profile.hcommons.org")
        self.assertEqual(
            args.args[1], "https://profile.hcommons.org/cilogon/callback/"
        )
        self.assertEqual(_next_url_in_state(args.kwargs["state"]), "")
