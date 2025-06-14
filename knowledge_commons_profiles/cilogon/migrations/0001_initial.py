# Generated by Django 5.1.8 on 2025-05-16 15:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("newprofile", "0035_alter_profile_email_alter_profile_orcid"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubAssociation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sub", models.CharField(max_length=255)),
                (
                    "profile",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="newprofile.profile",
                    ),
                ),
            ],
        ),
    ]
