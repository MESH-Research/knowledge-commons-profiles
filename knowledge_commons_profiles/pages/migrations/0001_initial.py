from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SitePage",
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
                (
                    "slug",
                    models.SlugField(
                        help_text="URL path identifier for this page (e.g. 'registration-start').",
                        max_length=200,
                        unique=True,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="Page title displayed in the heading and browser tab.",
                        max_length=300,
                    ),
                ),
                (
                    "body",
                    models.TextField(
                        help_text="HTML content for the page body.",
                    ),
                ),
                (
                    "cta_url",
                    models.CharField(
                        blank=True,
                        help_text="Optional call-to-action URL. Can be an absolute path (e.g. '/login/') or a full URL.",
                        max_length=500,
                    ),
                ),
                (
                    "cta_text",
                    models.CharField(
                        blank=True,
                        help_text="Text for the call-to-action button (if cta_url is set).",
                        max_length=200,
                    ),
                ),
            ],
            options={
                "verbose_name": "Site Page",
                "verbose_name_plural": "Site Pages",
            },
        ),
    ]
