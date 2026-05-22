"""Custom model fields for the newprofile app."""

from django.db import models


class CICharField(models.CharField):
    """A ``CharField`` backed by PostgreSQL's ``citext`` type.

    The original mixed-case value is stored unchanged; equality comparisons,
    ``IN`` lookups and unique indexes are case-insensitive. ``max_length`` is
    still enforced by Django's validation but not by the database column.

    Requires the ``citext`` extension to be installed in the database.
    """

    def db_type(self, connection):
        return "citext"
