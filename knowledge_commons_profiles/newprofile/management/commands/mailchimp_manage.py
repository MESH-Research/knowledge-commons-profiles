"""
Management command for Mailchimp subscriber operations.

Supports adding, updating email, and unsubscribing users.
All actions accept either a username (looks up the Profile) or
an email address directly via --email.
"""

import hashlib
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_add_new_user_to_mailchimp,
)
from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_mailchimp_request,
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
        add_group = add_parser.add_mutually_exclusive_group(required=True)
        add_group.add_argument(
            "username",
            nargs="?",
            type=str,
            help="Username to subscribe (looks up Profile)",
        )
        add_group.add_argument(
            "--email",
            type=str,
            help="Subscribe this email directly (no Profile lookup)",
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
        unsub_group = unsub_parser.add_mutually_exclusive_group(
            required=True
        )
        unsub_group.add_argument(
            "username",
            nargs="?",
            type=str,
            help="Username to unsubscribe (looks up Profile)",
        )
        unsub_group.add_argument(
            "--email",
            type=str,
            help="Unsubscribe this email directly (no Profile lookup)",
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
            if options.get("email"):
                self._handle_add_email(options["email"], dry_run)
            else:
                self._handle_add(options["username"], dry_run)
        elif action == "update-email":
            self._handle_update_email(
                options["old_email"], options["new_email"], dry_run
            )
        elif action == "unsubscribe":
            if options.get("email"):
                self._handle_unsubscribe_email(
                    options["email"], dry_run
                )
            else:
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
            self.style.SUCCESS(
                f"Mailchimp add completed for {username}."
            )
        )

    def _handle_add_email(self, email, dry_run):
        self.stdout.write(f"Email: {email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — would subscribe this email "
                    "to Mailchimp."
                )
            )
            return

        payload = {
            "email_address": email,
            "status": "subscribed",
            "tags": ["hc", "new-user"],
            "interests": {
                settings.MAILCHIMP_NEWSLETTER_GROUP_ID: True,
            },
        }

        response = hcommons_mailchimp_request(
            f"/lists/{settings.MAILCHIMP_LIST_ID}/members",
            "POST",
            payload,
        )

        if isinstance(response, dict) and "id" in response:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Subscribed {email} to Mailchimp "
                    f"(status: {response.get('status')})."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Failed to subscribe {email}. "
                    f"Response: {response}"
                )
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
                self.style.SUCCESS(
                    "Mailchimp subscriber email updated."
                )
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

    def _handle_unsubscribe_email(self, email, dry_run):
        self.stdout.write(f"Email: {email}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — would unsubscribe this email "
                    "from Mailchimp."
                )
            )
            return

        subscriber_hash = hashlib.md5(  # noqa: S324
            email.lower().encode()
        ).hexdigest()

        response = hcommons_mailchimp_request(
            f"/lists/{settings.MAILCHIMP_LIST_ID}"
            f"/members/{subscriber_hash}",
            "DELETE",
            {},
        )

        if response is None or (
            isinstance(response, dict) and not response.get("status")
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Unsubscribed {email} from Mailchimp."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Failed to unsubscribe {email}. "
                    f"Response: {response}"
                )
            )
