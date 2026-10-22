# tests/test_people_by_username.py
import base64
from datetime import timedelta
from math import ceil
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.views import members
from knowledge_commons_profiles.newprofile.views.members import _decode_cursor
from knowledge_commons_profiles.newprofile.views.members import _encode_cursor
from knowledge_commons_profiles.newprofile.views.members import _page_bounds
from knowledge_commons_profiles.newprofile.views.members import _prefix_count_qs
from knowledge_commons_profiles.newprofile.views.members import (
    people_by_username,
)

User = get_user_model()


class CursorHelpersTests(TestCase):
    def test_encode_decode_roundtrip(self):
        payload = {"username": "alice", "id": 42}
        token = _encode_cursor(payload)
        # token is URL-safe base64 over a compact JSON encoding
        # sanity: decodes without error and matches original dict
        decoded = _decode_cursor(token)
        self.assertEqual(decoded, payload)

        # Ensure it is indeed URL-safe base64
        # (no assertion on content, just that decode path works)
        base64.urlsafe_b64decode(token.encode())

    def test_page_bounds(self):
        # PAGE_SIZE-independent helper: just checks math
        start, end = _page_bounds(1)
        self.assertEqual((start, end), (0, 0 + members.PAGE_SIZE))
        start, end = _page_bounds(3)
        self.assertEqual(
            (start, end),
            (
                (3 - 1) * members.PAGE_SIZE,
                (3 - 1) * members.PAGE_SIZE + members.PAGE_SIZE,
            ),
        )


class PrefixCountTests(TestCase):
    def setUp(self):
        self.p1 = Profile.objects.create(username="alice", name="Alice A")
        self.p2 = Profile.objects.create(username="alice2", name="Alice B")
        self.p3 = Profile.objects.create(username="bob", name="Bob A")
        self.p4 = Profile.objects.create(username="carol", name="Carol A")

        self.qs = members.with_last_login(
            Profile.objects.filter(name__isnull=False).exclude(
                name__exact=""
            )
        ).order_by(*members.LISTING_ORDER)

    def test_prefix_count_qs_at_beginning(self):
        # Count rows <= ("alice", p1.id)
        cnt = _prefix_count_qs(
            self.qs, {"username": "alice", "id": self.p1.id}
        )
        self.assertEqual(cnt, 1)

    def test_prefix_count_qs_with_same_username(self):
        # Count rows <= ("alice2", p2.id) should include alice and alice2
        cnt = _prefix_count_qs(
            self.qs, {"username": "alice2", "id": self.p2.id}
        )
        self.assertEqual(cnt, 2)

    def test_prefix_count_qs_across_usernames(self):
        # Count rows <= ("bob", p3.id) should include alice, alice2, and bob
        cnt = _prefix_count_qs(self.qs, {"username": "bob", "id": self.p3.id})
        self.assertEqual(cnt, 3)


class PeopleByUsernameViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_profiles(self, records):
        """
        records: list of (username, name)
        returns created list in DB insertion order for reference
        """
        created = []
        for u, n in records:
            created.append(Profile.objects.create(username=u, name=n))
        return created

    def _stub_render(self, request, template_name, context):
        # Minimal stub to capture outputs of the view
        return SimpleNamespace(
            status_code=200,
            template_name=template_name,
            context=context,
        )

    def _encode(self, username, id_):
        return _encode_cursor({"username": username, "id": id_})

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_first_page_when_less_than_page_size(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.side_effect = lambda p: f"IMG:{p.username}"

        # Make fewer than PAGE_SIZE; we'll patch PAGE_SIZE=5 for this test
        data = [("alice", "Alice"), ("bob", "Bob"), ("carol", "Carol")]
        self._make_profiles(data)

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 5
        ):
            request = self.factory.get("/members")
            response = people_by_username(request)

        ctx = response.context
        self.assertEqual(response.template_name, "newprofile/members.html")

        # profiles sorted by (username,id)
        usernames = [p.username for p in ctx["profiles"]]
        self.assertEqual(usernames, ["alice", "bob", "carol"])

        # final_image attached from get_profile_photo
        self.assertTrue(
            all(hasattr(p, "final_image") for p in ctx["profiles"])
        )
        self.assertEqual(
            [p.final_image for p in ctx["profiles"]],
            ["IMG:alice", "IMG:bob", "IMG:carol"],
        )

        # has_next False because we had < PAGE_SIZE
        self.assertFalse(ctx["has_next"])
        self.assertFalse(ctx["has_prev"])
        self.assertIsNone(ctx["next_cursor"])
        self.assertIsNone(ctx["prev_cursor"])

        # page_count = 1, current_page = 1
        self.assertEqual(ctx["total_count"], len(data))
        self.assertEqual(ctx["page_count"], 1)
        self.assertEqual(ctx["current_page"], 1)
        self.assertEqual(ctx["page_size"], 5)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_first_page_exactly_page_size_plus_one_sets_has_next(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.side_effect = lambda p: "IMG"

        # Create 6 records; PAGE_SIZE=5 means first page returns 5
        # and sets has_next=True
        records = [
            ("alice", "A1"),
            ("alice2", "A2"),
            ("bob", "B1"),
            ("carol", "C1"),
            ("dave", "D1"),
            ("erin", "E1"),
        ]
        _ = self._make_profiles(records)

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 5
        ):
            request = self.factory.get("/members")
            response = people_by_username(request)

        ctx = response.context
        self.assertTrue(ctx["has_next"])
        self.assertFalse(ctx["has_prev"])
        self.assertEqual(len(ctx["profiles"]), 5)

        # next_cursor points at the last returned row
        last_row = ctx["profiles"][-1]
        decoded = _decode_cursor(ctx["next_cursor"])
        self.assertEqual(
            (decoded["username"], decoded["id"]),
            (last_row.username, last_row.id),
        )
        self.assertIsNone(ctx["prev_cursor"])

        # page_count should be ceil(6/5)=2
        self.assertEqual(ctx["page_count"], ceil(6 / 5))

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_next_page_with_cursor(self, mock_get_photo, mock_render):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        # Make 7 profiles; PAGE_SIZE=3 → pages: [0..2], [3..5], [6]
        _ = self._make_profiles(
            [
                ("alice", "A1"),
                ("alice2", "A2"),
                ("bob", "B1"),
                ("carol", "C1"),
                ("dave", "D1"),
                ("erin", "E1"),
                ("frank", "F1"),
            ]
        )

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 3
        ):
            # First page
            r1 = people_by_username(self.factory.get("/members"))
            c1 = r1.context
            self.assertTrue(c1["has_next"])
            self.assertFalse(c1["has_prev"])
            self.assertEqual(len(c1["profiles"]), 3)
            next1 = c1["next_cursor"]
            self.assertIsNotNone(next1)

            # Second page using next cursor
            r2 = people_by_username(
                self.factory.get("/members", {"cursor": next1, "dir": "next"})
            )
            c2 = r2.context
            self.assertTrue(
                c2["has_next"]
            )  # because there is still a third page
            self.assertTrue(c2["has_prev"])
            self.assertEqual(len(c2["profiles"]), 3)
            next2 = c2["next_cursor"]
            prev2 = c2["prev_cursor"]
            self.assertIsNotNone(next2)
            self.assertIsNotNone(prev2)

            # Third page using next cursor again
            r3 = people_by_username(
                self.factory.get("/members", {"cursor": next2, "dir": "next"})
            )
            c3 = r3.context
            self.assertFalse(c3["has_next"])
            self.assertTrue(c3["has_prev"])
            self.assertEqual(len(c3["profiles"]), 1)
            self.assertIsNone(c3["next_cursor"])
            self.assertIsNotNone(c3["prev_cursor"])

            # Current page numbers should be 1, 2, 3
            self.assertEqual(c1["current_page"], 1)
            self.assertEqual(c2["current_page"], 2)
            self.assertEqual(c3["current_page"], 3)

            # page_count = ceil(7/3) = 3
            self.assertEqual(c3["page_count"], 3)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_prev_direction_uses_reverse_window(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        _ = self._make_profiles(
            [
                ("alice", "A1"),
                ("bob", "B1"),
                ("carol", "C1"),
                ("dave", "D1"),
            ]
        )

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 2
        ):
            # Page 1
            r1 = people_by_username(self.factory.get("/members"))
            c1 = r1.context
            self.assertTrue(c1["has_next"])
            self.assertFalse(c1["has_prev"])
            next1 = c1["next_cursor"]

            # Page 2 (go next)
            r2 = people_by_username(
                self.factory.get("/members", {"cursor": next1, "dir": "next"})
            )
            c2 = r2.context
            self.assertFalse(c2["has_next"])  # no more pages
            self.assertTrue(c2["has_prev"])
            prev2 = c2["prev_cursor"]

            # Now go back using dir=prev
            r_prev = people_by_username(
                self.factory.get("/members", {"cursor": prev2, "dir": "prev"})
            )
            cp = r_prev.context
            # When going prev from second page start, we should land on
            # the first page again
            self.assertTrue(cp["has_next"])
            self.assertFalse(cp["has_prev"])
            self.assertEqual(
                [p.username for p in cp["profiles"]],
                [p.username for p in c1["profiles"]],
            )

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_empty_queryset(self, mock_get_photo, mock_render):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 10
        ):
            r = people_by_username(self.factory.get("/members"))
            c = r.context

        self.assertEqual(c["profiles"], [])
        self.assertFalse(c["has_next"])
        self.assertFalse(c["has_prev"])
        self.assertIsNone(c["next_cursor"])
        self.assertIsNone(c["prev_cursor"])
        self.assertEqual(c["total_count"], 0)
        self.assertEqual(c["page_count"], 1)
        self.assertEqual(c["current_page"], 1)
        self.assertEqual(c["page_size"], 10)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_current_page_prefix_count_alignment(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        # 10 records; PAGE_SIZE=4 → pages of size [4,4,2]
        _ = self._make_profiles(
            [
                ("a1", "1"),
                ("a2", "2"),
                ("b1", "3"),
                ("b2", "4"),
                ("c1", "5"),
                ("d1", "6"),
                ("e1", "7"),
                ("f1", "8"),
                ("g1", "9"),
                ("h1", "10"),
            ]
        )

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 4
        ):
            # First page
            r1 = people_by_username(self.factory.get("/members"))
            c1 = r1.context
            self.assertEqual(c1["current_page"], 1)
            n1 = c1["next_cursor"]

            # Second page via cursor
            r2 = people_by_username(
                self.factory.get("/members", {"cursor": n1, "dir": "next"})
            )
            c2 = r2.context
            self.assertEqual(c2["current_page"], 2)
            n2 = c2["next_cursor"]

            # Third page via cursor
            r3 = people_by_username(
                self.factory.get("/members", {"cursor": n2, "dir": "next"})
            )
            c3 = r3.context
            self.assertEqual(c3["current_page"], 3)
            self.assertEqual(c3["page_count"], 3)
            self.assertEqual(c3["total_count"], 10)


class InterestFilterTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.interest_dh = AcademicInterest.objects.create(
            text="Digital Humanities"
        )
        self.interest_ml = AcademicInterest.objects.create(
            text="Machine Learning"
        )

        self.alice = Profile.objects.create(username="alice", name="Alice A")
        self.alice.academic_interests.add(self.interest_dh, self.interest_ml)

        self.bob = Profile.objects.create(username="bob", name="Bob B")
        self.bob.academic_interests.add(self.interest_dh)

        self.carol = Profile.objects.create(username="carol", name="Carol C")
        self.carol.academic_interests.add(self.interest_ml)

        self.dave = Profile.objects.create(username="dave", name="Dave D")
        # dave has no interests

    def _stub_render(self, request, template_name, context):
        return SimpleNamespace(
            status_code=200,
            template_name=template_name,
            context=context,
        )

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_interest_filter_returns_matching_profiles(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        request = self.factory.get(
            "/members", {"interest": "Digital Humanities"}
        )
        response = people_by_username(request)
        ctx = response.context

        usernames = [p.username for p in ctx["profiles"]]
        self.assertEqual(usernames, ["alice", "bob"])
        self.assertEqual(ctx["interest_filter"], "Digital Humanities")
        self.assertEqual(ctx["total_count"], 2)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_interest_filter_no_matches(self, mock_get_photo, mock_render):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        request = self.factory.get(
            "/members", {"interest": "Nonexistent Interest"}
        )
        response = people_by_username(request)
        ctx = response.context

        self.assertEqual(ctx["profiles"], [])
        self.assertEqual(ctx["interest_filter"], "Nonexistent Interest")
        self.assertEqual(ctx["total_count"], 0)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_no_interest_param_returns_all_profiles(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 25
        ):
            request = self.factory.get("/members")
            response = people_by_username(request)

        ctx = response.context
        self.assertEqual(ctx["total_count"], 4)
        self.assertIsNone(ctx["interest_filter"])

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_interest_filter_prefetches_interests(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        request = self.factory.get(
            "/members", {"interest": "Digital Humanities"}
        )
        response = people_by_username(request)
        ctx = response.context

        for p in ctx["profiles"]:
            self.assertTrue(hasattr(p, "display_interests"))
            interest_texts = [i.text for i in p.display_interests]
            self.assertIn("Digital Humanities", interest_texts)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_regular_listing_prefetches_interests(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 25
        ):
            request = self.factory.get("/members")
            response = people_by_username(request)

        ctx = response.context
        for p in ctx["profiles"]:
            self.assertTrue(hasattr(p, "display_interests"))

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_interest_filter_preserves_cursor_pagination(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 1
        ):
            request = self.factory.get(
                "/members", {"interest": "Digital Humanities"}
            )
            r1 = people_by_username(request)
            c1 = r1.context

            self.assertEqual(len(c1["profiles"]), 1)
            self.assertTrue(c1["has_next"])
            self.assertEqual(c1["interest_filter"], "Digital Humanities")

            r2 = people_by_username(
                self.factory.get(
                    "/members",
                    {
                        "interest": "Digital Humanities",
                        "cursor": c1["next_cursor"],
                        "dir": "next",
                    },
                )
            )
            c2 = r2.context
            self.assertEqual(len(c2["profiles"]), 1)
            self.assertFalse(c2["has_next"])
            self.assertEqual(c2["interest_filter"], "Digital Humanities")


class RecencyOrderingHelperTests(TestCase):
    """Pure helpers behind the login-recency listing order."""

    def test_parse_key_tolerates_legacy_cursor_without_last_login(self):
        last_login, username, id_ = members._parse_key(
            {"username": "alice", "id": 7}
        )
        self.assertIsNone(last_login)
        self.assertEqual((username, id_), ("alice", 7))

    def test_cursor_payload_roundtrips_through_encode_decode(self):
        when = timezone.now().replace(microsecond=123456)
        profile = SimpleNamespace(last_login=when, username="alice", id=3)
        token = _encode_cursor(members._cursor_payload(profile))
        parsed = members._parse_key(_decode_cursor(token))
        self.assertEqual(parsed, (when, "alice", 3))

    def test_cursor_payload_roundtrips_with_no_login(self):
        profile = SimpleNamespace(last_login=None, username="bob", id=9)
        token = _encode_cursor(members._cursor_payload(profile))
        parsed = members._parse_key(_decode_cursor(token))
        self.assertEqual(parsed, (None, "bob", 9))

    def test_sort_key_puts_recent_logins_first_and_never_last(self):
        now = timezone.now()
        rows = [
            SimpleNamespace(last_login=None, username="zed", id=1),
            SimpleNamespace(
                last_login=now - timedelta(days=2), username="old", id=2
            ),
            SimpleNamespace(last_login=None, username="amy", id=3),
            SimpleNamespace(last_login=now, username="new", id=4),
            SimpleNamespace(last_login=now, username="new", id=0),
        ]
        ordered = sorted(rows, key=members._sort_key)
        self.assertEqual(
            [(r.username, r.id) for r in ordered],
            [("new", 0), ("new", 4), ("old", 2), ("amy", 3), ("zed", 1)],
        )


class RecencyOrderingQueryTests(TestCase):
    """Database-backed ordering, cursor filtering and prefix counts."""

    def setUp(self):
        self.now = timezone.now()
        self.alice = Profile.objects.create(username="alice", name="Alice")
        self.bob = Profile.objects.create(username="bob", name="Bob")
        self.carol = Profile.objects.create(username="carol", name="Carol")
        self.dave = Profile.objects.create(username="dave", name="Dave")
        User.objects.create(username="carol", last_login=self.now)
        User.objects.create(
            username="alice", last_login=self.now - timedelta(days=1)
        )
        # bob has a user who has never completed a login
        User.objects.create(username="bob", last_login=None)
        self.qs = members.with_last_login(
            Profile.objects.filter(name__isnull=False)
        ).order_by(*members.LISTING_ORDER)

    def test_with_last_login_reads_auth_user_last_login(self):
        by_name = {p.username: p.last_login for p in self.qs}
        self.assertEqual(by_name["carol"], self.now)
        self.assertEqual(by_name["alice"], self.now - timedelta(days=1))
        self.assertIsNone(by_name["bob"])
        self.assertIsNone(by_name["dave"])

    def test_listing_order_is_recent_first_then_username(self):
        self.assertEqual(
            [p.username for p in self.qs],
            ["carol", "alice", "bob", "dave"],
        )

    def test_after_q_selects_rows_following_a_logged_in_cursor(self):
        key = members._cursor_payload(self.qs.get(username="alice"))
        self.assertEqual(
            [p.username for p in self.qs.filter(members._after_q(key))],
            ["bob", "dave"],
        )

    def test_after_q_selects_rows_following_a_never_logged_in_cursor(self):
        key = members._cursor_payload(self.qs.get(username="bob"))
        self.assertEqual(
            [p.username for p in self.qs.filter(members._after_q(key))],
            ["dave"],
        )

    def test_before_q_selects_rows_preceding_a_never_logged_in_cursor(self):
        key = members._cursor_payload(self.qs.get(username="bob"))
        self.assertEqual(
            [p.username for p in self.qs.filter(members._before_q(key))],
            ["carol", "alice"],
        )

    def test_before_q_selects_rows_preceding_a_logged_in_cursor(self):
        key = members._cursor_payload(self.qs.get(username="alice"))
        self.assertEqual(
            [p.username for p in self.qs.filter(members._before_q(key))],
            ["carol"],
        )

    def test_prefix_count_counts_rows_up_to_and_including_key(self):
        self.assertEqual(
            _prefix_count_qs(
                self.qs,
                members._cursor_payload(self.qs.get(username="carol")),
            ),
            1,
        )
        self.assertEqual(
            _prefix_count_qs(
                self.qs,
                members._cursor_payload(self.qs.get(username="bob")),
            ),
            3,
        )


class RecencyOrderingViewTests(TestCase):
    """The members views list recently active members first."""

    def setUp(self):
        self.factory = RequestFactory()
        now = timezone.now()
        for username in ("alice", "bob", "carol", "dave", "erin"):
            Profile.objects.create(username=username, name=username.title())
        User.objects.create(username="dave", last_login=now)
        User.objects.create(
            username="bob", last_login=now - timedelta(hours=3)
        )
        self.expected = ["dave", "bob", "alice", "carol", "erin"]

    def _stub_render(self, request, template_name, context):
        return SimpleNamespace(
            status_code=200, template_name=template_name, context=context
        )

    def _usernames(self, response):
        return [p.username for p in response.context["profiles"]]

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_first_page_is_ordered_by_recency(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"
        response = people_by_username(self.factory.get("/members"))
        self.assertEqual(self._usernames(response), self.expected)

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_cursor_pages_cross_the_login_boundary_in_order(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"

        with patch(
            "knowledge_commons_profiles.newprofile.views.members.PAGE_SIZE", 2
        ):
            r1 = people_by_username(self.factory.get("/members"))
            self.assertEqual(self._usernames(r1), self.expected[:2])
            self.assertEqual(r1.context["current_page"], 1)

            r2 = people_by_username(
                self.factory.get(
                    "/members",
                    {"cursor": r1.context["next_cursor"], "dir": "next"},
                )
            )
            self.assertEqual(self._usernames(r2), self.expected[2:4])
            self.assertEqual(r2.context["current_page"], 2)
            self.assertTrue(r2.context["has_prev"])
            self.assertTrue(r2.context["has_next"])

            r3 = people_by_username(
                self.factory.get(
                    "/members",
                    {"cursor": r2.context["next_cursor"], "dir": "next"},
                )
            )
            self.assertEqual(self._usernames(r3), self.expected[4:])
            self.assertEqual(r3.context["current_page"], 3)
            self.assertFalse(r3.context["has_next"])

            back = people_by_username(
                self.factory.get(
                    "/members",
                    {"cursor": r3.context["prev_cursor"], "dir": "prev"},
                )
            )
            self.assertEqual(self._usernames(back), self.expected[2:4])
            self.assertEqual(back.context["current_page"], 2)

            back_again = people_by_username(
                self.factory.get(
                    "/members",
                    {"cursor": back.context["prev_cursor"], "dir": "prev"},
                )
            )
            self.assertEqual(self._usernames(back_again), self.expected[:2])
            self.assertFalse(back_again.context["has_prev"])

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_search_results_are_ordered_by_recency(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"
        # "e" matches alice, dave and erin; dave is the only one of
        # those who has logged in, so he leads and the rest are A-Z
        response = people_by_username(
            self.factory.post("/members", {"username": "e"})
        )
        self.assertEqual(
            self._usernames(response), ["dave", "alice", "erin"]
        )

    @patch("knowledge_commons_profiles.newprofile.views.members.render")
    @patch(
        "knowledge_commons_profiles.newprofile.views.members.get_profile_photo"
    )
    def test_interest_filter_is_ordered_by_recency(
        self, mock_get_photo, mock_render
    ):
        mock_render.side_effect = self._stub_render
        mock_get_photo.return_value = "IMG"
        interest = AcademicInterest.objects.create(text="Book History")
        for username in ("alice", "bob", "carol"):
            Profile.objects.get(username=username).academic_interests.add(
                interest
            )
        response = people_by_username(
            self.factory.get("/members", {"interest": "Book History"})
        )
        self.assertEqual(self._usernames(response), ["bob", "alice", "carol"])

    def test_rendered_listing_places_recent_members_first(self):
        response = self.client.get("/members/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        positions = [
            html.index(reverse("profile", args=[u])) for u in self.expected
        ]
        self.assertEqual(positions, sorted(positions))
