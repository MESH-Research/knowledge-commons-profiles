"""
Management command to clean up double-escaped HTML entities in individual
profile fields.

Usage:
    ./manage.py sanitize_profile jackwchen
    ./manage.py sanitize_profile jackwchen --field about_user
    ./manage.py sanitize_profile jackwchen --dry-run
"""

import html as html_module

from django.core.management.base import BaseCommand

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import sanitize_html

HTML_FIELDS = [
    "about_user",
    "education",
    "upcoming_talks",
    "projects",
    "publications",
    "memberships",
]


class Command(BaseCommand):
    help = (
        "Unescape and sanitize HTML in a profile's rich-text fields. "
        "Use when imported profiles display stray escaped tags like "
        "&lt;span&gt;."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            help="Username of the profile to sanitize.",
        )
        parser.add_argument(
            "--field",
            choices=HTML_FIELDS,
            default=None,
            help=(
                "Sanitize only this field. "
                "If omitted, all HTML fields are sanitized."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would change without saving.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        field = options.get("field")
        dry_run = options["dry_run"]

        if field and field not in HTML_FIELDS:
            self.stderr.write(
                self.style.ERROR(
                    f"'{field}' is not a valid HTML field. "
                    f"Choose from: {', '.join(HTML_FIELDS)}"
                )
            )
            return

        try:
            profile = Profile.objects.get(username=username)
        except Profile.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"Profile not found for username '{username}'."
                )
            )
            return

        fields_to_clean = [field] if field else HTML_FIELDS
        changed = []

        for f in fields_to_clean:
            old_value = getattr(profile, f)
            if not old_value:
                continue

            new_value = sanitize_html(html_module.unescape(old_value))

            if old_value != new_value:
                changed.append(f)
                preview_old = old_value[:120]
                preview_new = new_value[:120]
                if dry_run:
                    self.stdout.write(
                        f"Would update {f}:\n"
                        f"  before: {preview_old}...\n"
                        f"  after:  {preview_new}...\n"
                    )
                else:
                    setattr(profile, f, new_value)
                    self.stdout.write(
                        f"Updated {f}:\n"
                        f"  before: {preview_old}...\n"
                        f"  after:  {preview_new}...\n"
                    )

        if not changed:
            self.stdout.write("No changes needed.")
            return

        if not dry_run:
            profile.save(update_fields=changed)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Saved {len(changed)} field(s) for '{username}'."
                )
            )
