# Generated by Django 5.1.4 on 2025-02-06 14:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0008_profile_show_commons_groups_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="academicinterest",
            name="text",
            field=models.CharField(db_index=True, max_length=255),
        ),
    ]
