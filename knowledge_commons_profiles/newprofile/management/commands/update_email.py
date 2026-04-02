"""
Management command to update a user's primary email address.

Updates the profile, Mailchimp subscriber, and WordPress in the same
sequence as the web UI flow.
"""

import logging

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from knowledge_commons_profiles.cilogon.oauth import sync_email_to_wordpress
from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_update_user_email_in_mailchimp,
)
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update a user's primary email address"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username to update")
        parser.add_argument("new_email", type=str, help="New primary email")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without making changes",
        )

    def handle(self, *args, **options):
        username = options["username"]
        new_email = options["new_email"]
        dry_run = options["dry_run"]

        try:
            profile = Profile.objects.get(username=username)
        except Profile.DoesNotExist as err:
            msg = f"No profile found for username: {username}"
            raise CommandError(msg) from err

        old_email = profile.email

        if old_email == new_email:
            self.stdout.write(
                f"Email for {username} is already {new_email}, "
                "nothing to do."
            )
            return

        self.stdout.write(f"Username:  {username}")
        self.stdout.write(f"Old email: {old_email}")
        self.stdout.write(f"New email: {new_email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDry run — no changes made.")
            )
            return

        # Move old primary to secondaries if not already there
        if old_email not in profile.emails:
            profile.emails.append(old_email)

        # Set new primary
        profile.email = new_email

        # Remove new email from secondaries if present
        if new_email in profile.emails:
            profile.emails.remove(new_email)

        profile.emails = sorted(profile.emails)
        profile.save()

        self.stdout.write("Profile updated.")

        # Update Mailchimp subscriber email
        mc_result = hcommons_update_user_email_in_mailchimp(
            old_email, new_email
        )
        if mc_result:
            self.stdout.write("Mailchimp subscriber email updated.")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Mailchimp update skipped or failed "
                    "(see logs for details)."
                )
            )

        # Sync to WordPress
        wp_result = sync_email_to_wordpress(
            username=username, email=new_email
        )
        if wp_result:
            self.stdout.write("WordPress email synced.")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "WordPress sync failed (see logs for details)."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nEmail for {username} updated to {new_email}."
            )
        )
