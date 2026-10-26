from django.test import SimpleTestCase

from knowledge_commons_profiles.up_salesforce.soql import soql_quote


class SoqlQuoteTests(SimpleTestCase):
    def test_plain_value_is_wrapped_in_single_quotes(self):
        self.assertEqual(soql_quote("ada@example.org"), "'ada@example.org'")

    def test_single_quote_is_escaped(self):
        self.assertEqual(
            soql_quote("o'brien@example.org"), r"'o\'brien@example.org'"
        )

    def test_backslash_is_escaped(self):
        self.assertEqual(soql_quote("a\\b"), r"'a\\b'")

    def test_injection_attempt_cannot_close_the_literal(self):
        quoted = soql_quote("x' OR Name != '")
        self.assertEqual(quoted.count("'") - quoted.count("\\'"), 2)
