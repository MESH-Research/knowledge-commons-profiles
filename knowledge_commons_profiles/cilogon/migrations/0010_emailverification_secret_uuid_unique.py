# Generated manually for security improvement

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("cilogon", "0009_encrypt_tokens"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailverification",
            name="secret_uuid",
            field=models.CharField(
                db_index=True, max_length=255, unique=True
            ),
        ),
    ]
