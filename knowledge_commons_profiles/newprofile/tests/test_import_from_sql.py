"""
Tests for the import_from_sql management command's parsing of the
sqloxide AST.

The AST shape has changed across sqloxide releases (notably between
the 0.1.x and 0.61.x lines), so the parser needs to be exercised
against real ``parse_sql`` output, not just hand-crafted dicts.
Catching shape regressions here is the entire point of these tests --
if a future sqloxide bump alters the JSON layout again, these tests
should fail before the importer is run on a real dump.
"""

from django.test import TestCase
from sqloxide import parse_sql

from knowledge_commons_profiles.newprofile.management.commands.import_from_sql import (  # noqa: E501
    Command,
)


def _parse_insert(sql):
    """Parse a single INSERT statement and return the Insert AST node."""
    return parse_sql(sql, dialect="mysql")[0]["Insert"]


class ImportFromSqlParserTests(TestCase):
    """Cover the AST-shape differences across sqloxide versions."""

    def test_extract_table_name_new_sqloxide_shape(self):
        """sqloxide >=0.61 wraps the identifier in an "Identifier" dict."""
        val = _parse_insert(
            "INSERT INTO `wp_users` (`id`) VALUES (1);",
        )

        self.assertEqual(Command._extract_table_name(val), "wp_users")

    def test_extract_table_name_legacy_sqloxide_shape(self):
        """sqloxide ~0.1.56 placed value/quote_style directly on the entry."""
        val = {
            "table": {
                "TableName": [
                    {"value": "wp_bp_xprofile_data", "quote_style": "`"},
                ],
            },
        }

        self.assertEqual(
            Command._extract_table_name(val),
            "wp_bp_xprofile_data",
        )

    def test_build_final_dict_extracts_string_value(self):
        """Single-quoted strings must round-trip through _build_final_dict."""
        val = _parse_insert(
            "INSERT INTO `wp_users` (`user_login`) VALUES ('alice');",
        )
        row = val["source"]["body"]["Values"]["rows"][0]
        final_dict = {}

        Command._build_final_dict(
            "user_login",
            {"user_login": 0},
            final_dict,
            row,
        )

        self.assertEqual(final_dict, {"user_login": "alice"})

    def test_build_final_dict_extracts_number_value(self):
        """Numeric literals must be unwrapped to their string form."""
        val = _parse_insert(
            "INSERT INTO `wp_users` (`id`) VALUES (42);",
        )
        row = val["source"]["body"]["Values"]["rows"][0]
        final_dict = {}

        Command._build_final_dict("id", {"id": 0}, final_dict, row)

        self.assertEqual(final_dict, {"id": "42"})

    def test_handle_insert_collects_target_table_rows(self):
        """End-to-end: a real INSERT for a target table is parsed correctly."""
        cmd = Command()
        val = _parse_insert(
            "INSERT INTO `wp_users` "
            "(`id`, `user_login`, `user_email`) "
            "VALUES (7, 'alice', 'a@b.com');",
        )

        all_tables_rows = [[]]
        desired_fields_list = [["id", "user_login", "user_email"]]
        field_indexes = [{"id": 0, "user_login": 1, "user_email": 2}]
        statement_counters = [0]
        target_tables = ["wp_users"]

        cmd._handle_insert(
            all_tables_rows,
            desired_fields_list,
            field_indexes,
            "Insert",
            statement_counters,
            target_tables,
            val,
        )

        self.assertEqual(
            all_tables_rows,
            [[{"id": "7", "user_login": "alice", "user_email": "a@b.com"}]],
        )

    def test_handle_insert_skips_non_target_tables(self):
        """Tables outside ``target_tables`` should not produce rows."""
        cmd = Command()
        val = _parse_insert(
            "INSERT INTO `wp_options` (`option_id`) VALUES (1);",
        )

        all_tables_rows = [[]]
        desired_fields_list = [["id"]]
        field_indexes = [{"id": 0}]
        statement_counters = [0]
        target_tables = ["wp_users"]

        cmd._handle_insert(
            all_tables_rows,
            desired_fields_list,
            field_indexes,
            "Insert",
            statement_counters,
            target_tables,
            val,
        )

        self.assertEqual(all_tables_rows, [[]])
