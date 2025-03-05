# Generated by Django 5.1.4 on 2025-02-06 10:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "newprofile",
            "0007_profile_show_blog_posts_alter_wppostsubtable_table",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="show_commons_groups",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="show_mastodon_feed",
            field=models.BooleanField(default=True),
        ),
    ]
