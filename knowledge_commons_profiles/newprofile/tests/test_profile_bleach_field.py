"""
Tests for ProfileBleachField.

The class is retained only so that historical migration 0014 can still be
imported. It must not depend on the unmaintained django-bleach package
(issue #679), and it must behave as a plain text field: values round-trip
unchanged in both directions.
"""

import importlib

from django.db import models
from django.test import SimpleTestCase
from django.utils.safestring import SafeString

from knowledge_commons_profiles.newprofile.models import ProfileBleachField


class ProfileBleachFieldTests(SimpleTestCase):
    """ProfileBleachField behaves as a plain TextField without django-bleach."""

    def test_does_not_depend_on_django_bleach(self):
        """No class in the MRO may come from the django_bleach package."""
        offending = [
            cls
            for cls in ProfileBleachField.__mro__
            if cls.__module__.startswith("django_bleach")
        ]
        self.assertEqual(offending, [])

    def test_is_a_text_field(self):
        """The field is a TextField so the DB column type is unchanged."""
        field = ProfileBleachField(blank=True, null=True)
        self.assertIsInstance(field, models.TextField)
        self.assertEqual(field.get_internal_type(), "TextField")

    def test_from_db_value_returns_plain_string(self):
        """Values read from the DB are returned as-is, not as SafeString."""
        field = ProfileBleachField()
        value = "<b>bold</b> & <i>italic</i>"
        result = field.from_db_value(value, None, None)
        self.assertEqual(result, value)
        self.assertNotIsInstance(result, SafeString)

    def test_from_db_value_passes_none_through(self):
        """NULL columns stay None."""
        field = ProfileBleachField()
        self.assertIsNone(field.from_db_value(None, None, None))

    def test_pre_save_returns_attribute_unchanged(self):
        """pre_save returns the instance attribute without rewriting it."""
        field = ProfileBleachField()
        field.set_attributes_from_name("about_user")

        class Holder:
            about_user = "<p>Hello <script>x</script></p>"

        result = field.pre_save(Holder(), add=True)
        self.assertEqual(result, Holder.about_user)
        self.assertNotIsInstance(result, SafeString)

    def test_pre_save_passes_none_through(self):
        """A None attribute is returned as None."""
        field = ProfileBleachField()
        field.set_attributes_from_name("about_user")

        class Holder:
            about_user = None

        self.assertIsNone(field.pre_save(Holder(), add=True))

    def test_historical_migration_0014_still_imports(self):
        """Migration 0014 references the class by dotted path."""
        module = importlib.import_module(
            "knowledge_commons_profiles.newprofile.migrations."
            "0014_wpbpactivity_wpbpactivitymeta_wpbpfollow_and_more"
        )
        field_classes = {
            type(op.field)
            for op in module.Migration.operations
            if hasattr(op, "field")
        }
        self.assertIn(ProfileBleachField, field_classes)
