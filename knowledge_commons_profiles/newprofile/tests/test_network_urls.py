"""
Tests for network-aware, environment-aware group URL construction.
"""

from unittest import mock

from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile import network_urls

_OVERRIDES = {"msu": {"dev": "msucommons-dev.org", "main": "commons.msu.edu"}}


class NetworkDomainTests(SimpleTestCase):
    """network_domain maps a society id to a Commons domain."""

    def test_base_society_returns_default_domain(self):
        self.assertEqual(
            network_urls.network_domain("hc", "hcommons-dev.org"),
            "hcommons-dev.org",
        )

    def test_empty_society_returns_default_domain(self):
        self.assertEqual(
            network_urls.network_domain("", "hcommons-dev.org"),
            "hcommons-dev.org",
        )

    def test_none_society_returns_default_domain(self):
        self.assertEqual(
            network_urls.network_domain(None, "hcommons-dev.org"),
            "hcommons-dev.org",
        )

    def test_network_society_gets_subdomain(self):
        self.assertEqual(
            network_urls.network_domain("mla", "hcommons-dev.org"),
            "mla.hcommons-dev.org",
        )

    @override_settings(
        NETWORK_DOMAIN_OVERRIDES=_OVERRIDES,
        NETWORK_DOMAIN_ENVIRONMENT="main",
    )
    def test_override_used_for_environment(self):
        self.assertEqual(
            network_urls.network_domain("msu", "hcommons.org"),
            "commons.msu.edu",
        )

    @override_settings(
        NETWORK_DOMAIN_OVERRIDES=_OVERRIDES,
        NETWORK_DOMAIN_ENVIRONMENT="dev",
    )
    def test_override_falls_back_to_subdomain_for_other_network(self):
        # a network with no override entry still gets the subdomain form
        self.assertEqual(
            network_urls.network_domain("mla", "hcommons-dev.org"),
            "mla.hcommons-dev.org",
        )


class GroupUrlTests(SimpleTestCase):
    """group_url builds the full resolving URL."""

    @override_settings(NAV_DEFAULT_DOMAIN="hcommons-dev.org")
    def test_network_group_url(self):
        self.assertEqual(
            network_urls.group_url("mla", "20th-and-21st-century-american"),
            "https://mla.hcommons-dev.org/groups/"
            "20th-and-21st-century-american/",
        )

    @override_settings(NAV_DEFAULT_DOMAIN="hcommons-dev.org")
    def test_base_group_url(self):
        self.assertEqual(
            network_urls.group_url("hc", "open-art-histories"),
            "https://hcommons-dev.org/groups/open-art-histories/",
        )

    @override_settings(NAV_DEFAULT_DOMAIN="hcommons-dev.org")
    def test_untyped_group_uses_base_domain(self):
        self.assertEqual(
            network_urls.group_url(None, "open-art-histories"),
            "https://hcommons-dev.org/groups/open-art-histories/",
        )

    @override_settings(NAV_DEFAULT_DOMAIN="hcommons.org")
    def test_default_domain_comes_from_settings(self):
        self.assertEqual(
            network_urls.group_url("mla", "g"),
            "https://mla.hcommons.org/groups/g/",
        )

    def test_explicit_default_domain_overrides_settings(self):
        self.assertEqual(
            network_urls.group_url("mla", "g", default_domain="example.org"),
            "https://mla.example.org/groups/g/",
        )


class SocietyIdsForGroupsTests(TestCase):
    """society_ids_for_groups resolves each group's bp_group_type slug."""

    def test_empty_input_returns_empty_map(self):
        self.assertEqual(network_urls.society_ids_for_groups([]), {})

    @mock.patch.object(network_urls, "WpTerm")
    @mock.patch.object(network_urls, "WpTermRelationships")
    def test_maps_group_id_to_slug(self, mock_rel, mock_term):
        mock_rel.objects.filter.return_value.values_list.return_value = [
            (101, 5),
            (102, 6),
        ]
        mock_term.objects.filter.return_value.values_list.return_value = [
            (5, "mla"),
            (6, "hc"),
        ]

        result = network_urls.society_ids_for_groups([101, 102])

        self.assertEqual(result, {101: "mla", 102: "hc"})

    @mock.patch.object(network_urls, "WpTerm")
    @mock.patch.object(network_urls, "WpTermRelationships")
    def test_group_without_type_is_absent(self, mock_rel, mock_term):
        # only group 101 has a bp_group_type row
        mock_rel.objects.filter.return_value.values_list.return_value = [
            (101, 5),
        ]
        mock_term.objects.filter.return_value.values_list.return_value = [
            (5, "arlisna"),
        ]

        result = network_urls.society_ids_for_groups([101, 102])

        self.assertEqual(result, {101: "arlisna"})
        self.assertNotIn(102, result)

    @mock.patch.object(network_urls, "WpTerm")
    @mock.patch.object(network_urls, "WpTermRelationships")
    def test_only_bp_group_type_rows_are_used(self, mock_rel, mock_term):
        # object_id is shared across object types, so the DB only yields the
        # group-type row when the query constrains to the bp_group_type
        # taxonomy. A fake that honours that filter proves, via the output,
        # that the constraint is applied — without it the slug is lost.
        def fake_filter(**kwargs):
            qs = mock.MagicMock()
            if kwargs.get("term_taxonomy__taxonomy") == "bp_group_type":
                qs.values_list.return_value = [(101, 5)]
            else:
                qs.values_list.return_value = []
            return qs

        mock_rel.objects.filter.side_effect = fake_filter
        mock_term.objects.filter.return_value.values_list.return_value = [
            (5, "mla"),
        ]

        result = network_urls.society_ids_for_groups([101])

        self.assertEqual(result, {101: "mla"})
