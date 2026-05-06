"""
Data migration to normalise legacy values stored in Profile.facebook,
Profile.linkedin and Profile.website (issue #544).

Earlier versions of the profile system stored bare usernames or
scheme-less URLs in these fields. The new edit form is URL-validated;
without this migration, opening any old profile in the new edit view
would surface validation errors and existing profile pages would
render broken `<a href="bareusername">` links. The form-side coercion
helper handles future input; this migration takes care of rows that
will never be touched again unless the user re-edits.
"""

from django.db import migrations

from knowledge_commons_profiles.newprofile.utils import coerce_social_url

FACEBOOK_PREFIX = "https://facebook.com/"
LINKEDIN_PREFIX = "https://linkedin.com/in/"


def normalise_legacy_social_urls(apps, schema_editor):
    Profile = apps.get_model("newprofile", "Profile")

    fields = (
        ("facebook", FACEBOOK_PREFIX),
        ("linkedin", LINKEDIN_PREFIX),
        ("website", None),
    )

    for profile in Profile.objects.iterator():
        changed = False
        for name, prefix in fields:
            current = getattr(profile, name) or ""
            coerced = coerce_social_url(current, prefix)
            if coerced != current:
                setattr(profile, name, coerced)
                changed = True
        if changed:
            profile.save(
                update_fields=[name for name, _ in fields],
            )


def noop(apps, schema_editor):
    """Reverse migration is a no-op: there is no general way to recover
    the original raw values once they've been coerced."""


class Migration(migrations.Migration):

    dependencies = [
        ("newprofile", "0052_unique_profile_username"),
    ]

    operations = [
        migrations.RunPython(normalise_legacy_social_urls, noop),
    ]
