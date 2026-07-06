from django.db import migrations

# Initial prohibited username terms. Each is a plain prefix term: matching
# ignores case, hyphens and underscores, so a single entry (e.g.
# "knowledgecommons") also blocks "knowledge_commons", "Knowledge-Commons" and
# "knowledgecommons123". Staff can prune or extend this list in the admin.
SEED_TERMS = [
    # Platform / institution names
    ("knowledgecommons", "Platform name"),
    ("humanitiescommons", "Platform name"),
    ("hcommons", "Platform name"),
    ("kcworks", "Platform name"),
    # Administrative / support / official roles
    ("admin", "Administrative role"),
    ("administrator", "Administrative role"),
    ("superuser", "Administrative role"),
    ("root", "Administrative role"),
    ("staff", "Administrative role"),
    ("support", "Support role"),
    ("techsupport", "Support role"),
    ("helpdesk", "Support role"),
    ("moderator", "Moderation role"),
    ("sysadmin", "Administrative role"),
    ("system", "System-sounding name"),
    ("official", "Official-sounding name"),
    ("security", "Security-sounding name"),
    ("abuse", "Reserved mailbox name"),
    ("postmaster", "Reserved mailbox name"),
    ("webmaster", "Reserved mailbox name"),
    ("noreply", "Reserved mailbox name"),
]


def seed_reserved_usernames(apps, schema_editor):
    ReservedUsername = apps.get_model("cilogon", "ReservedUsername")
    for pattern, note in SEED_TERMS:
        # get_or_create keeps this idempotent and never overwrites a term an
        # admin may already have edited.
        ReservedUsername.objects.get_or_create(
            pattern=pattern, defaults={"note": note, "active": True}
        )


def remove_reserved_usernames(apps, schema_editor):
    ReservedUsername = apps.get_model("cilogon", "ReservedUsername")
    ReservedUsername.objects.filter(
        pattern__in=[pattern for pattern, _ in SEED_TERMS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cilogon", "0013_reservedusername"),
    ]

    operations = [
        migrations.RunPython(
            seed_reserved_usernames, remove_reserved_usernames
        ),
    ]
