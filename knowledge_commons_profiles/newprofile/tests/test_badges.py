"""
Tests for the staff-managed profile badges feature.
"""

import json
import tempfile
from http import HTTPStatus

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from knowledge_commons_profiles.newprofile.forms import ProfileForm
from knowledge_commons_profiles.newprofile.models import Badge
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import ProfileBadge
from knowledge_commons_profiles.newprofile.tests.model_factories import (
    ProfileFactory,
)
from knowledge_commons_profiles.newprofile.utils import process_orders

# a valid one-pixel PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x87\xa1J\xf6\x00\x00\x00\x00IEND\xaeB`\x82"
)

MEDIA_ROOT = tempfile.mkdtemp()


def make_badge(title, order, alt_text=""):
    """Create a badge with a stored one-pixel image."""
    badge = Badge(
        title=title,
        alt_text=alt_text or f"{title} description",
        order=order,
    )
    badge.image.save(f"{title}.png", ContentFile(PNG_BYTES), save=True)
    return badge


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BadgeModelTests(TestCase):
    """Behaviour of the Badge and ProfileBadge models."""

    def test_badges_are_ordered_by_order_field(self):
        make_badge("zeta-test", order=30)
        make_badge("alpha-test", order=10)
        make_badge("mid-test", order=20)

        titles = list(
            Badge.objects.filter(title__endswith="-test").values_list(
                "title", flat=True
            )
        )
        assert titles == ["alpha-test", "mid-test", "zeta-test"]

    def test_profile_badges_relation_is_ordered(self):
        profile = ProfileFactory()
        second = make_badge("second-test", order=2)
        first = make_badge("first-test", order=1)

        ProfileBadge.objects.create(profile=profile, badge=second)
        ProfileBadge.objects.create(profile=profile, badge=first)

        assert list(profile.badges.all()) == [first, second]

    def test_profile_cannot_hold_same_badge_twice(self):
        profile = ProfileFactory()
        badge = make_badge("dupe-test", order=1)

        ProfileBadge.objects.create(profile=profile, badge=badge)
        with self.assertRaises(IntegrityError):
            ProfileBadge.objects.create(profile=profile, badge=badge)

    def test_show_badges_defaults_to_true(self):
        assert Profile(username="someone").show_badges is True


class BadgeSeedTests(TestCase):
    """The sample badges are seeded by migration."""

    def test_six_seeded_badges_exist(self):
        # NOTE: content-level test; delete before merge if it constrains
        # editing seeded badges
        seeded_count = 6
        assert Badge.objects.count() >= seeded_count


class ProcessOrdersBadgeTests(TestCase):
    """Badges appear first in the right-hand column by default."""

    def test_badges_first_when_no_saved_order(self):
        _, right = process_orders([], [])
        assert right[0] == "badges"

    def test_badges_prepended_for_existing_saved_order(self):
        # a user who saved an order before badges existed
        _, right = process_orders([], ["cv", "academic_interests"])
        assert right[0] == "badges"
        assert right.index("cv") < right.index("academic_interests")

    def test_saved_badge_position_is_honoured(self):
        _, right = process_orders([], ["cv", "badges"])
        assert right.index("cv") < right.index("badges")


class BadgeProfileFormTests(TestCase):
    """Users may hide the box but cannot award or remove badges."""

    def test_show_badges_is_editable_by_user(self):
        assert "show_badges" in ProfileForm().fields

    def test_badge_awards_are_not_editable_by_user(self):
        fields = ProfileForm().fields
        assert "badges" not in fields
        assert "profiles" not in fields


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BadgeFragmentTests(TestCase):
    """Rendering of the badges box on the profile page."""

    def render(self, profile):
        return render_to_string(
            "newprofile/fragments/badges.html", {"profile": profile}
        )

    def test_badges_render_with_alt_text_and_title(self):
        profile = ProfileFactory()
        badge = make_badge(
            "fragment-test", order=1, alt_text="A shiny fragment badge"
        )
        ProfileBadge.objects.create(profile=profile, badge=badge)

        html = self.render(profile)
        assert "A shiny fragment badge" in html
        assert "fragment-test" in html
        assert badge.image.url in html

    def test_box_hidden_when_show_badges_off(self):
        profile = ProfileFactory(show_badges=False)
        badge = make_badge("hidden-test", order=1)
        ProfileBadge.objects.create(profile=profile, badge=badge)

        html = self.render(profile)
        assert "hidden-test" not in html
        assert "content-card" not in html

    def test_box_hidden_when_profile_has_no_badges(self):
        profile = ProfileFactory()

        html = self.render(profile)
        assert "content-card" not in html

    def test_edit_fragment_offers_show_badges_toggle(self):
        profile = ProfileFactory()
        html = render_to_string(
            "newprofile/fragments/badges_edit.html",
            {"profile": profile, "form": ProfileForm(instance=profile)},
        )
        assert "show_badges" in html
        assert "sortable-item" in html


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class OrderedBadgesTests(TestCase):
    """Profile.ordered_badges: user customisation with default fallback."""

    def setUp(self):
        self.profile = ProfileFactory()

    def award(self, badge, order=None):
        return ProfileBadge.objects.create(
            profile=self.profile, badge=badge, order=order
        )

    def test_default_order_used_when_user_has_not_customised(self):
        zeta = make_badge("zeta-default-test", order=30)
        alpha = make_badge("alpha-default-test", order=10)
        mid = make_badge("mid-default-test", order=20)
        self.award(zeta)
        self.award(alpha)
        self.award(mid)

        assert list(self.profile.ordered_badges) == [alpha, mid, zeta]

    def test_customised_order_overrides_default(self):
        zeta = make_badge("zeta-custom-test", order=30)
        alpha = make_badge("alpha-custom-test", order=10)
        self.award(zeta, order=0)
        self.award(alpha, order=1)

        assert list(self.profile.ordered_badges) == [zeta, alpha]

    def test_unpositioned_badges_follow_customised_in_default_order(self):
        # the user ordered two badges, then staff awarded two more
        first = make_badge("first-mixed-test", order=40)
        second = make_badge("second-mixed-test", order=30)
        newer_b = make_badge("newer-b-mixed-test", order=20)
        newer_a = make_badge("newer-a-mixed-test", order=10)
        self.award(first, order=0)
        self.award(second, order=1)
        self.award(newer_b)
        self.award(newer_a)

        assert list(self.profile.ordered_badges) == [
            first,
            second,
            newer_a,
            newer_b,
        ]

    def test_other_profiles_customisation_does_not_leak(self):
        alpha = make_badge("alpha-leak-test", order=10)
        beta = make_badge("beta-leak-test", order=20)
        self.award(alpha)
        self.award(beta)

        other = ProfileFactory()
        ProfileBadge.objects.create(profile=other, badge=beta, order=0)
        ProfileBadge.objects.create(profile=other, badge=alpha, order=1)

        assert list(self.profile.ordered_badges) == [alpha, beta]


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SaveBadgesOrderViewTests(TestCase):
    """The AJAX endpoint that persists a user's badge ordering."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="badge-sorter", password="password"
        )
        self.profile = ProfileFactory(username="badge-sorter")
        self.alpha = make_badge("alpha-save-test", order=10)
        self.beta = make_badge("beta-save-test", order=20)
        ProfileBadge.objects.create(profile=self.profile, badge=self.alpha)
        ProfileBadge.objects.create(profile=self.profile, badge=self.beta)
        self.url = reverse("save_badges_order")

    def post_order(self, items):
        return self.client.post(
            self.url,
            data=json.dumps({"item_order": items}),
            content_type="application/json",
        )

    def test_posting_an_order_saves_it(self):
        self.client.force_login(self.user)
        response = self.post_order(
            [f"badge-{self.beta.pk}", f"badge-{self.alpha.pk}"]
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["success"] is True
        assert list(self.profile.ordered_badges) == [self.beta, self.alpha]

    def test_reordering_twice_keeps_the_latest_order(self):
        self.client.force_login(self.user)
        self.post_order([f"badge-{self.beta.pk}", f"badge-{self.alpha.pk}"])
        self.post_order([f"badge-{self.alpha.pk}", f"badge-{self.beta.pk}"])

        assert list(self.profile.ordered_badges) == [self.alpha, self.beta]

    def test_requires_login(self):
        response = self.post_order([f"badge-{self.alpha.pk}"])
        assert response.status_code == HTTPStatus.FOUND

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_cannot_reorder_another_users_awards(self):
        other_profile = ProfileFactory(username="badge-holder")
        gamma = make_badge("gamma-save-test", order=30)
        other_award = ProfileBadge.objects.create(
            profile=other_profile, badge=gamma
        )
        self.client.force_login(self.user)
        self.post_order([f"badge-{gamma.pk}"])

        other_award.refresh_from_db()
        assert other_award.order is None

    def test_invalid_json_returns_error(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data="not-json", content_type="application/json"
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json()["success"] is False


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BadgeOrderingRenderTests(TestCase):
    """Customised ordering is reflected wherever badges render."""

    def test_public_fragment_renders_in_customised_order(self):
        profile = ProfileFactory()
        alpha = make_badge("alpha-render-test", order=10)
        beta = make_badge("beta-render-test", order=20)
        ProfileBadge.objects.create(profile=profile, badge=alpha, order=1)
        ProfileBadge.objects.create(profile=profile, badge=beta, order=0)

        html = render_to_string(
            "newprofile/fragments/badges.html", {"profile": profile}
        )
        assert html.index("beta-render-test") < html.index("alpha-render-test")

    def test_edit_fragment_lists_badges_as_sortable_items(self):
        profile = ProfileFactory()
        badge = make_badge("edit-render-test", order=1)
        ProfileBadge.objects.create(profile=profile, badge=badge)

        html = render_to_string(
            "newprofile/fragments/badges_edit.html",
            {"profile": profile, "form": ProfileForm(instance=profile)},
        )
        assert f'id="badge-{badge.pk}"' in html
        assert 'id="badge-sort-list"' in html

    def test_edit_fragment_lists_badges_in_customised_order(self):
        profile = ProfileFactory()
        alpha = make_badge("alpha-edit-order-test", order=10)
        beta = make_badge("beta-edit-order-test", order=20)
        ProfileBadge.objects.create(profile=profile, badge=alpha, order=1)
        ProfileBadge.objects.create(profile=profile, badge=beta, order=0)

        html = render_to_string(
            "newprofile/fragments/badges_edit.html",
            {"profile": profile, "form": ProfileForm(instance=profile)},
        )
        assert html.index("beta-edit-order-test") < html.index(
            "alpha-edit-order-test"
        )

    def test_edit_fragment_omits_list_when_profile_has_no_badges(self):
        profile = ProfileFactory()
        html = render_to_string(
            "newprofile/fragments/badges_edit.html",
            {"profile": profile, "form": ProfileForm(instance=profile)},
        )
        assert 'id="badge-sort-list"' not in html

    def test_edit_page_wires_the_badge_sort_save_url(self):
        user = User.objects.create_user(
            username="badge-page-user", password="password"
        )
        profile = ProfileFactory(username="badge-page-user")
        badge = make_badge("edit-page-test", order=1)
        ProfileBadge.objects.create(profile=profile, badge=badge)
        self.client.force_login(user)

        response = self.client.get(reverse("edit_profile"))
        content = response.content.decode()
        assert reverse("save_badges_order") in content
        assert 'id="save-badges-order"' in content


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MassAwardAdminTests(TestCase):
    """Staff mass award/removal via the Django admin."""

    def setUp(self):
        self.staff = User.objects.create_superuser(
            username="admin-user", password="password"
        )
        self.badge = make_badge("mass-test", order=1)
        self.url = reverse(
            "admin:newprofile_badge_mass_award", args=[self.badge.pk]
        )
        self.alice = ProfileFactory(username="alice")
        self.bob = ProfileFactory(username="bob")

    def award(self, profile):
        ProfileBadge.objects.create(profile=profile, badge=self.badge)

    def holders(self):
        return set(
            self.badge.profiles.values_list("username", flat=True)
        )

    def test_mass_award_creates_awards(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            {"usernames": "alice, bob", "action": "award"},
            follow=True,
        )
        assert response.status_code == HTTPStatus.OK
        assert self.holders() == {"alice", "bob"}

    def test_mass_award_reports_unknown_usernames(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            {"usernames": "alice, nonexistent-user", "action": "award"},
            follow=True,
        )
        assert self.holders() == {"alice"}
        messages = [str(m) for m in response.context["messages"]]
        assert any("nonexistent-user" in m for m in messages)

    def test_mass_award_skips_existing_holders(self):
        self.award(self.alice)
        self.client.force_login(self.staff)
        self.client.post(
            self.url,
            {"usernames": "alice, bob", "action": "award"},
            follow=True,
        )
        assert self.holders() == {"alice", "bob"}
        assert (
            ProfileBadge.objects.filter(
                badge=self.badge, profile=self.alice
            ).count()
            == 1
        )

    def test_mass_remove_deletes_awards(self):
        self.award(self.alice)
        self.award(self.bob)
        self.client.force_login(self.staff)
        self.client.post(
            self.url,
            {"usernames": "alice", "action": "remove"},
            follow=True,
        )
        assert self.holders() == {"bob"}

    def test_non_staff_cannot_mass_award(self):
        outsider = User.objects.create_user(
            username="outsider", password="password"
        )
        self.client.force_login(outsider)
        response = self.client.post(
            self.url,
            {"usernames": "alice", "action": "award"},
        )
        # bounced to the admin login, nothing awarded
        assert response.status_code == HTTPStatus.FOUND
        assert self.holders() == set()
