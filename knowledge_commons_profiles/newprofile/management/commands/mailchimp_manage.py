"""
Management command for Mailchimp subscriber operations.

Supports adding, updating email, and unsubscribing users.
"""

import logging

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_add_new_user_to_mailchimp,
)
from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_remove_user_from_mailchimp,
)
from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_update_user_email_in_mailchimp,
)
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manage Mailchimp subscribers: add, update-email, unsubscribe"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", help="Action")
        subparsers.required = True

        # add
        add_parser = subparsers.add_parser(
            "add", help="Add a user to Mailchimp"
        )
        add_parser.add_argument(
            "username", type=str, help="Username to subscribe"
        )
        add_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without making changes",
        )

        # update-email
        update_parser = subparsers.add_parser(
            "update-email",
            help="Update a subscriber's email in Mailchimp",
        )
        update_parser.add_argument(
            "old_email", type=str, help="Current email in Mailchimp"
        )
        update_parser.add_argument(
            "new_email", type=str, help="New email address"
        )
        update_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without making changes",
        )

        # unsubscribe
        unsub_parser = subparsers.add_parser(
            "unsubscribe",
            help="Remove/archive a user from Mailchimp",
        )
        unsub_parser.add_argument(
            "username", type=str, help="Username to unsubscribe"
        )
        unsub_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without making changes",
        )

    def handle(self, *args, **options):
        action = options["action"]
        dry_run = options.get("dry_run", False)

        if action == "add":
            self._handle_add(options["username"], dry_run)
        elif action == "update-email":
            self._handle_update_email(
                options["old_email"], options["new_email"], dry_run
            )
        elif action == "unsubscribe":
            self._handle_unsubscribe(options["username"], dry_run)

    def _handle_add(self, username, dry_run):
        try:
            profile = Profile.objects.get(username=username)
        except Profile.DoesNotExist as err:
            msg = f"No profile found for username: {username}"
            raise CommandError(msg) from err

        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Email:    {profile.email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — would add this user to Mailchimp."
                )
            )
            return

        hcommons_add_new_user_to_mailchimp(username)
        self.stdout.write(
            self.style.SUCCESS(f"Mailchimp add completed for {username}.")
        )

    def _handle_update_email(self, old_email, new_email, dry_run):
        self.stdout.write(f"Old email: {old_email}")
        self.stdout.write(f"New email: {new_email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — would update subscriber email "
                    "in Mailchimp."
                )
            )
            return

        result = hcommons_update_user_email_in_mailchimp(
            old_email, new_email
        )
        if result:
            self.stdout.write(
                self.style.SUCCESS("Mailchimp subscriber email updated.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Mailchimp update failed or skipped "
                    "(see logs for details)."
                )
            )

    def _handle_unsubscribe(self, username, dry_run):
        try:
            profile = Profile.objects.get(username=username)
        except Profile.DoesNotExist as err:
            msg = f"No profile found for username: {username}"
            raise CommandError(msg) from err

        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Email:    {profile.email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — would unsubscribe this user "
                    "from Mailchimp."
                )
            )
            return

        hcommons_remove_user_from_mailchimp(username)
        self.stdout.write(
            self.style.SUCCESS(
                f"Mailchimp unsubscribe completed for {username}."
            )
        )
