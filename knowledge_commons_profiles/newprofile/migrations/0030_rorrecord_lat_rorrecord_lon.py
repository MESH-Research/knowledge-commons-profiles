# Generated by Django 5.1.8 on 2025-04-19 16:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0029_remove_rorlookup_wp_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="rorrecord",
            name="lat",
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name="rorrecord",
            name="lon",
            field=models.FloatField(null=True),
        ),
    ]
