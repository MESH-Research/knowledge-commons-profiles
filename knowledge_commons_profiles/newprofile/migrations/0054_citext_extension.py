"""Enable the PostgreSQL ``citext`` extension.

Required before ``Profile.username`` can be converted to the case-insensitive
``citext`` type. ``CREATE EXTENSION`` needs elevated database privileges.
"""

from django.contrib.postgres.operations import CITextExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("newprofile", "0053_normalise_legacy_social_urls"),
    ]

    operations = [
        CITextExtension(),
    ]
