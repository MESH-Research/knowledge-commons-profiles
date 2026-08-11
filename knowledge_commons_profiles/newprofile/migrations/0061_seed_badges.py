"""
Seed the six sample badges shipped in newprofile/fixtures/badges/.
"""

from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

SEED_COUNT = 6

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "badges"


def seed_badges(apps, schema_editor):
    badge_model = apps.get_model("newprofile", "Badge")

    for number in range(1, SEED_COUNT + 1):
        title = f"Badge {number}"

        if badge_model.objects.filter(title=title).exists():
            continue

        source = FIXTURE_DIR / f"{number}.png"
        if not source.exists():
            continue

        name = f"badges/seed-{number}.png"
        if not default_storage.exists(name):
            with source.open("rb") as image_file:
                name = default_storage.save(name, File(image_file))

        badge_model.objects.create(
            title=title,
            alt_text=f"Sample badge {number}",
            image=name,
            order=number,
        )


def unseed_badges(apps, schema_editor):
    badge_model = apps.get_model("newprofile", "Badge")
    titles = [f"Badge {number}" for number in range(1, SEED_COUNT + 1)]
    badge_model.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("newprofile", "0060_badges"),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
