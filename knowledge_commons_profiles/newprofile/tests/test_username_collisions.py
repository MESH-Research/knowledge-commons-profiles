"""Unit tests for the case-insensitive username collision helpers."""

from django.test import SimpleTestCase

from knowledge_commons_profiles.newprofile.username_collisions import (
    find_collision_groups,
)
from knowledge_commons_profiles.newprofile.username_collisions import (
    next_free_suffixed_name,
)
from knowledge_commons_profiles.newprofile.username_collisions import (
    plan_renames,
)


class FindCollisionGroupsTests(SimpleTestCase):
    """``find_collision_groups`` groups rows that collide case-insensitively."""

    def test_no_collisions_returns_empty(self):
        groups = find_collision_groups([(1, "alice"), (2, "bob")])
        self.assertEqual(groups, {})

    def test_groups_case_variants_under_lowercased_key(self):
        groups = find_collision_groups([(1, "alice"), (2, "Alice")])
        self.assertEqual(
            groups, {"alice": [(1, "alice"), (2, "Alice")]}
        )

    def test_group_members_sorted_by_id(self):
        groups = find_collision_groups([(5, "Alice"), (2, "alice")])
        self.assertEqual(
            groups["alice"], [(2, "alice"), (5, "Alice")]
        )

    def test_unique_usernames_are_not_grouped(self):
        groups = find_collision_groups(
            [(1, "alice"), (2, "Alice"), (3, "bob")]
        )
        self.assertNotIn("bob", groups)
        self.assertEqual(len(groups), 1)

    def test_multiple_independent_groups(self):
        groups = find_collision_groups(
            [(1, "alice"), (2, "ALICE"), (3, "bob"), (4, "Bob")]
        )
        self.assertEqual(set(groups), {"alice", "bob"})


class NextFreeSuffixedNameTests(SimpleTestCase):
    """``next_free_suffixed_name`` finds the smallest free numeric suffix."""

    def test_first_suffix_when_nothing_taken(self):
        self.assertEqual(
            next_free_suffixed_name("Alice", {"alice"}), "Alice_1"
        )

    def test_skips_taken_suffixes(self):
        self.assertEqual(
            next_free_suffixed_name("Alice", {"alice", "alice_1"}),
            "Alice_2",
        )

    def test_skips_run_of_taken_suffixes(self):
        taken = {"alice", "alice_1", "alice_2", "alice_3"}
        self.assertEqual(next_free_suffixed_name("Alice", taken), "Alice_4")

    def test_taken_check_is_case_insensitive(self):
        # "Alice_1" should be considered taken even though the taken set
        # stores the lower-cased form.
        self.assertEqual(
            next_free_suffixed_name("ALICE", {"alice", "alice_1"}),
            "ALICE_2",
        )

    def test_preserves_original_casing(self):
        result = next_free_suffixed_name("MixedName", {"mixedname"})
        self.assertEqual(result, "MixedName_1")


class PlanRenamesTests(SimpleTestCase):
    """``plan_renames`` keeps the oldest profile and renames the rest."""

    def test_no_collisions_returns_empty_plan(self):
        self.assertEqual(plan_renames([(1, "alice"), (2, "bob")]), [])

    def test_oldest_id_keeps_username(self):
        plan = plan_renames([(1, "alice"), (2, "Alice")])
        # Only the second (newer) profile is renamed.
        self.assertEqual(plan, [(2, "Alice", "Alice_1")])

    def test_oldest_is_determined_by_id_not_input_order(self):
        # "Alice" has the lower id, so it is kept; "alice" is renamed.
        plan = plan_renames([(5, "alice"), (2, "Alice")])
        self.assertEqual(plan, [(5, "alice", "alice_1")])

    def test_suffix_increments_across_a_group(self):
        plan = plan_renames(
            [(1, "alice"), (2, "Alice"), (3, "ALICE")]
        )
        self.assertEqual(
            plan,
            [(2, "Alice", "Alice_1"), (3, "ALICE", "ALICE_2")],
        )

    def test_new_name_avoids_pre_existing_username(self):
        # A separate, non-colliding profile already holds "Alice_1", so the
        # renamed profile must skip to "Alice_2".
        plan = plan_renames(
            [(1, "alice"), (2, "Alice"), (3, "Alice_1")]
        )
        self.assertEqual(plan, [(2, "Alice", "Alice_2")])

    def test_suffix_appended_to_original_case(self):
        plan = plan_renames([(1, "mixedname"), (2, "MixedName")])
        self.assertEqual(plan, [(2, "MixedName", "MixedName_1")])

    def test_renamed_names_are_collision_free(self):
        plan = plan_renames(
            [(1, "alice"), (2, "Alice"), (3, "ALICE"), (4, "aliCE")]
        )
        new_names = [new.lower() for _id, _old, new in plan]
        self.assertEqual(len(new_names), len(set(new_names)))

    def test_independent_groups_both_resolved(self):
        plan = plan_renames(
            [(1, "alice"), (2, "Alice"), (3, "bob"), (4, "BOB")]
        )
        renamed_ids = {pid for pid, _old, _new in plan}
        self.assertEqual(renamed_ids, {2, 4})
