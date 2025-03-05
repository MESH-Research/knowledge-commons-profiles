# Generated by Django 5.1.6 on 2025-02-10 15:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "newprofile",
            "0012_remove_coverimage_user_coverimage_profile_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfileImage",
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
                ("thumb", models.CharField(max_length=255)),
                ("full", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        default="",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="newprofile.profile",
                    ),
                ),
            ],
        ),
    ]
