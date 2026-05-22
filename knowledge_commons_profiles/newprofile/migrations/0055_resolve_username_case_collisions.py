"""Resolve case-insensitive ``Profile.username`` collisions.

For each group of usernames that are equal once lower-cased, the oldest
profile (lowest id) keeps its username and the rest are renamed with a numeric
suffix. This must run before the unique index is rebuilt on the
case-insensitive ``citext`` column, which would otherwise reject the
collisions. Mirrors the ``resolve_username_case_collisions`` management
command, which can be run beforehand to preview the renames.
"""

from django.db import migrations

from knowledge_commons_profiles.newprofile.username_collisions import (
    plan_renames,
)


def resolve_collisions(apps, schema_editor):
    profile_model = apps.get_model("newprofile", "Profile")
    rows = list(
        profile_model.objects.values_list("id", "username").order_by("id")
    )
    for profile_id, _old, new_username in plan_renames(rows):
        profile_model.objects.filter(pk=profile_id).update(
            username=new_username
        )


def noop(apps, schema_editor):
    """Reverse is a no-op -- the original casing is not recorded."""


class Migration(migrations.Migration):

    dependencies = [
        ("newprofile", "0054_citext_extension"),
    ]

    operations = [
        migrations.RunPython(resolve_collisions, noop),
    ]
