# Generated by Django 5.1.8 on 2025-04-19 19:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0031_rorlookup_idx_rorlookup_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rorlookup",
            name="ror",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="newprofile.rorrecord",
            ),
        ),
    ]
