# Generated by Django 5.1.6 on 2025-02-10 13:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "newprofile",
            "0011_alter_profile_affiliation_alter_wppostsubtable_table_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="coverimage",
            name="profile",
            field=models.ForeignKey(
                default="",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="newprofile.profile",
            ),
        ),
    ]
