# Generated by Django 5.1.8 on 2025-05-20 07:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cilogon", "0002_tokenuseragentassociations"),
    ]

    operations = [
        migrations.AddField(
            model_name="tokenuseragentassociations",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
