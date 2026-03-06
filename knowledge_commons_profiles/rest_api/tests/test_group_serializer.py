"""
Tests for GroupDetailSerializer output format.
"""

from unittest import mock

from django.test import TestCase
from django.test import override_settings

from knowledge_commons_profiles.newprofile.models import WpBlog
from knowledge_commons_profiles.rest_api.serializers.serializers import (
    GroupDetailSerializer,
)

_MOCK_META = (
    "knowledge_commons_profiles.rest_api.serializers.serializers"
    ".WpBpGroupsGroupmeta.objects"
)
_MOCK_BLOG = (
    "knowledge_commons_profiles.rest_api.serializers.serializers"
    ".WpBlog.objects"
)


def _make_mock_group(
    pk=1004185,
    name="Open Art Histories",
    slug="open-art-histories",
    status="private",
    description="Open Art Histories group",
):
    """Create a mock WpBpGroup instance."""
    group = mock.MagicMock()
    group.pk = pk
    group.id = pk
    group.name = name
    group.slug = slug
    group.status = status
    group.description = description
    group.get_avatar.return_value = (
        "https://hcommons-dev.org/app/uploads"
        "/group-avatars/1004185/1686684096-bpfull.png"
    )
    return group


def _set_no_blog(mock_meta_qs):
    """Configure mock to return no blog_id meta."""
    qs = mock_meta_qs.filter.return_value
    qs.values_list.return_value.first.return_value = None


_GROUPS_URL = "https://hcommons-dev.org/groups/"


class TestGroupDetailSerializerFields(TestCase):
    """Test that GroupDetailSerializer returns the expected fields."""

    def setUp(self):
        self.group = _make_mock_group()

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_serializer_returns_expected_keys(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        serializer = GroupDetailSerializer(self.group)
        data = serializer.data

        expected_keys = {
            "id",
            "name",
            "url",
            "visibility",
            "description",
            "slug",
            "avatar",
            "groupblog",
            "upload_roles",
            "moderate_roles",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_slug_in_output_status_not(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        serializer = GroupDetailSerializer(self.group)
        data = serializer.data

        self.assertIn("slug", data)
        self.assertEqual(data["slug"], "open-art-histories")
        self.assertNotIn("status", data)


class TestGroupDetailSerializerUrl(TestCase):
    """Test the url field."""

    def setUp(self):
        self.group = _make_mock_group()

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_url_constructed_from_slug(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        serializer = GroupDetailSerializer(self.group)
        data = serializer.data

        self.assertEqual(
            data["url"],
            "https://hcommons-dev.org/groups/open-art-histories/",
        )


class TestGroupDetailSerializerVisibility(TestCase):
    """Test the visibility field maps from status."""

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_visibility_maps_from_status(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(status="private")
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["visibility"], "private")

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_visibility_public(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(status="public")
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["visibility"], "public")


class TestGroupDetailSerializerGroupblog(TestCase):
    """Test the groupblog field."""

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_groupblog_from_meta(
        self, mock_blog_qs, mock_meta_qs
    ):
        qs = mock_meta_qs.filter.return_value
        qs.values_list.return_value.first.return_value = 42
        mock_blog = mock.MagicMock()
        mock_blog.domain = "openarthistories.hcommons-dev.org"
        mock_blog.path = "/"
        mock_blog_qs.get.return_value = mock_blog

        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        self.assertEqual(
            data["groupblog"],
            "https://openarthistories.hcommons-dev.org/",
        )

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_groupblog_empty_when_no_meta(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)

        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["groupblog"], "")

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_groupblog_empty_when_blog_not_found(
        self, mock_blog_qs, mock_meta_qs
    ):
        qs = mock_meta_qs.filter.return_value
        qs.values_list.return_value.first.return_value = 99
        mock_blog_qs.get.side_effect = WpBlog.DoesNotExist

        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["groupblog"], "")


class TestGroupDetailSerializerRoles(TestCase):
    """Test the upload_roles and moderate_roles fields."""

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_upload_roles(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        self.assertEqual(
            data["upload_roles"],
            ["member", "moderator", "administrator"],
        )

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_moderate_roles(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        self.assertEqual(
            data["moderate_roles"],
            ["moderator", "administrator"],
        )


class TestGroupDetailSerializerWpUnslash(TestCase):
    """Test that WordPress backslash escaping is stripped from output."""

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_name_with_escaped_apostrophe(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(name="Ian\\'s test group D")
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["name"], "Ian's test group D")

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_description_with_escaped_apostrophe(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(
            description="A group about Ian\\'s research"
        )
        data = GroupDetailSerializer(group).data

        self.assertEqual(
            data["description"], "A group about Ian's research"
        )

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_name_with_escaped_double_quote(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(name='Say \\"hello\\"')
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["name"], 'Say "hello"')

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_name_without_escaping_unchanged(
        self, mock_blog_qs, mock_meta_qs
    ):
        _set_no_blog(mock_meta_qs)
        group = _make_mock_group(name="Normal Group Name")
        data = GroupDetailSerializer(group).data

        self.assertEqual(data["name"], "Normal Group Name")


class TestGroupDetailSerializerFullOutput(TestCase):
    """Integration test for the full expected output shape."""

    @override_settings(NAV_GROUPS_URL=_GROUPS_URL)
    @mock.patch(_MOCK_META)
    @mock.patch(_MOCK_BLOG)
    def test_full_output_matches_spec(
        self, mock_blog_qs, mock_meta_qs
    ):
        qs = mock_meta_qs.filter.return_value
        qs.values_list.return_value.first.return_value = 42
        mock_blog = mock.MagicMock()
        mock_blog.domain = "openarthistories.hcommons-dev.org"
        mock_blog.path = "/"
        mock_blog_qs.get.return_value = mock_blog

        group = _make_mock_group()
        data = GroupDetailSerializer(group).data

        expected = {
            "id": 1004185,
            "name": "Open Art Histories",
            "url": (
                "https://hcommons-dev.org/groups/"
                "open-art-histories/"
            ),
            "visibility": "private",
            "description": "Open Art Histories group",
            "slug": "open-art-histories",
            "avatar": (
                "https://hcommons-dev.org/app/uploads"
                "/group-avatars/1004185/"
                "1686684096-bpfull.png"
            ),
            "groupblog": (
                "https://openarthistories.hcommons-dev.org/"
            ),
            "upload_roles": [
                "member",
                "moderator",
                "administrator",
            ],
            "moderate_roles": [
                "moderator",
                "administrator",
            ],
        }
        self.assertEqual(data, expected)
