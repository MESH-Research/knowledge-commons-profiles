"""
Run the UP sync end to end with the External Client App credentials in
read-only mode: authenticate, look the profile(s) up in Salesforce, and
print what a real sync would write, without writing any of it.
"""

from dataclasses import asdict

from django.conf import settings
from django.core.management.base import CommandError

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.up_salesforce.dry_run import preview_sync
from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)
from knowledge_commons_profiles.up_salesforce.sync import SYNC_KEY
from knowledge_commons_profiles.up_salesforce.sync import UPExternalClientApp


def up_role_organizations() -> list[str]:
    """The role organizations mapped to UP in EXTERNAL_SYNC_CLASSES."""
    for class_name, organizations in settings.EXTERNAL_SYNC_CLASSES:
        if class_name == SYNC_KEY:
            return list(organizations)
    return []


class Command(UPSalesforceCommand):
    help = (
        "Dry-run the UP membership sync with the External Client App "
        "credentials: authenticate, query Salesforce and show what would "
        "change, writing nothing to the database"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--username",
            action="append",
            default=[],
            help="Profile username to preview (repeatable)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_profiles",
            help="Preview every profile (see --limit)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of profiles with --all (default 50)",
        )

    def _profiles(self, options):
        if options["username"]:
            profiles = []
            for username in options["username"]:
                try:
                    profiles.append(Profile.objects.get(username=username))
                except Profile.DoesNotExist as exc:
                    message = f"No profile with username {username!r}"
                    raise CommandError(message) from exc
            return profiles
        if options["all_profiles"]:
            return list(
                Profile.objects.order_by("username")[: options["limit"]]
            )
        message = "Select profiles with --username USERNAME or --all"
        raise CommandError(message)

    def run(self, *args, **options):
        profiles = self._profiles(options)

        client = self.get_client()
        # Authenticate up front so a bad secret is an error here rather
        # than silently turning every lookup into "not found".
        token = client.token_provider.get_token()
        sync = UPExternalClientApp(client=client)
        organizations = up_role_organizations()

        previews = [
            preview_sync(profile, sync, organizations) for profile in profiles
        ]

        if options["as_json"]:
            self.emit_json(
                [
                    {**asdict(preview), "would_change": preview.would_change}
                    for preview in previews
                ]
            )
            return

        self.stdout.write(
            self.style.WARNING("Dry run: nothing will be written.")
        )
        self.stdout.write(
            f"Authenticated to {token.instance_url} "
            f"(token {token.masked_token()})\n"
        )

        for preview in previews:
            self._print_preview(preview)

        changing = sum(1 for p in previews if p.would_change)
        self.stdout.write(
            f"Summary: {len(previews)} profile(s) previewed, {changing} "
            f"would change. No changes were written."
        )

    def _print_preview(self, preview):
        self.stdout.write(
            self.style.SUCCESS(preview.username)
            + f"  (emails: {', '.join(preview.emails) or 'none'})"
        )
        if preview.sync_id is None:
            self.stdout.write("  no contact found in UP; treated as non-member")
        self.stdout.write(
            f"  sync id   {preview.current_sync_id} -> {preview.sync_id}"
        )
        self.stdout.write(
            f"  member    {preview.current_is_member} -> {preview.is_member}"
        )
        self.stdout.write(
            f"  groups    {preview.current_groups} -> {preview.groups}"
        )
        for change in preview.role_changes:
            marker = "" if change.changed else "  (unchanged)"
            self.stdout.write(
                f"  role #{change.role_id} ({change.organization})  "
                f"{change.current_status} -> {change.new_status}{marker}"
            )
        self.stdout.write("")
