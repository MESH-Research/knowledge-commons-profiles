from django.db import migrations

REGISTRATION_START_BODY = """
<p>
  To create your Knowledge Commons account, you will first sign in through
  your institution or an identity provider (such as Google or ORCID) using
  our secure federated login system.
</p>

<p><strong>Here is how it works:</strong></p>

<ol>
  <li>Click the button below to begin. You will be redirected to choose your
  identity provider.</li>
  <li>Sign in with your chosen provider. This verifies your identity without
  Knowledge Commons ever seeing your password.</li>
  <li>After signing in, you will be asked to either connect an existing
  Knowledge Commons account or create a new one.</li>
</ol>

<p>
  You only need to do this once. After setup, you can log in at any time
  using the same identity provider.
</p>
""".strip()


def create_registration_start_page(apps, schema_editor):
    SitePage = apps.get_model("pages", "SitePage")
    SitePage.objects.get_or_create(
        slug="registration-start",
        defaults={
            "title": "Create Your Account",
            "body": REGISTRATION_START_BODY,
            "cta_url": "/login/",
            "cta_text": "Begin Registration",
        },
    )


def remove_registration_start_page(apps, schema_editor):
    SitePage = apps.get_model("pages", "SitePage")
    SitePage.objects.filter(slug="registration-start").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_registration_start_page,
            remove_registration_start_page,
        ),
    ]
