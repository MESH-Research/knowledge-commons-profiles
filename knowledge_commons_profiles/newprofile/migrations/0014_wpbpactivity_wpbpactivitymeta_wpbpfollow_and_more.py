# Generated by Django 5.0.12 on 2025-03-05 16:47

import knowledge_commons_profiles.newprofile.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0013_alter_wppostsubtable_table_profileimage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="about_user",
            field=knowledge_commons_profiles.newprofile.models.ProfileBleachField(
                blank=True, null=True
            ),
        ),
        migrations.AlterField(
            model_name="profile",
            name="education",
            field=knowledge_commons_profiles.newprofile.models.ProfileBleachField(
                blank=True, null=True
            ),
        ),
        migrations.AlterField(
            model_name="profile",
            name="publications",
            field=knowledge_commons_profiles.newprofile.models.ProfileBleachField(
                blank=True, null=True
            ),
        ),
    ]
