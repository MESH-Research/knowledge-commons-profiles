# Generated by Django 5.1.7 on 2025-04-01 09:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0017_profile_show_recent_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="show_commons_sites",
            field=models.BooleanField(default=True),
        ),
    ]
