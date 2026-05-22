"""Convert ``Profile.username`` to the case-insensitive ``citext`` type.

The stored values keep their original casing; equality comparisons and the
existing unique index become case-insensitive. The unique index created in
migration 0052 is rebuilt automatically by the column type change.
"""

from django.db import migrations

from knowledge_commons_profiles.newprofile.fields import CICharField


class Migration(migrations.Migration):

    dependencies = [
        ("newprofile", "0055_resolve_username_case_collisions"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="profile",
                    name="username",
                    field=CICharField(max_length=255, unique=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE newprofile_profile "
                        "ALTER COLUMN username TYPE citext "
                        "USING username::citext;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE newprofile_profile "
                        "ALTER COLUMN username TYPE varchar(255) "
                        "USING username::varchar(255);"
                    ),
                ),
            ],
        ),
    ]
