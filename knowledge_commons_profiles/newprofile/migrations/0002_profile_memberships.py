# Generated by Django 5.1.4 on 2025-01-23 17:10

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="memberships",
            field=models.TextField(blank=True, null=True),
        ),
    ]
