# Generated by Django 5.1.4 on 2025-02-05 11:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0006_profile_show_about_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="show_blog_posts",
            field=models.BooleanField(default=True),
        ),
    ]
