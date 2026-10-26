"""
Look up a UP Contact by email (or by a Profile's emails) and report
Commons eligibility, exercising the full sync path with the External
Client App credentials.
"""

from dataclasses import asdict

from django.core.management.base import CommandError

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)
from knowledge_commons_profiles.up_salesforce.sync import UPExternalClientApp


class Command(UPSalesforceCommand):
    help = (
        "Find a UP Salesforce Contact by email address(es) or by a Profile "
        "username and report whether they are Commons-eligible"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "emails", nargs="*", help="Email address(es) to search for"
        )
        parser.add_argument(
            "--username",
            help="Search with every email on this Profile instead",
        )

    def run(self, *args, **options):
        emails = list(options["emails"])

        if options["username"]:
            try:
                profile = Profile.objects.get(username=options["username"])
            except Profile.DoesNotExist as exc:
                message = f"No profile with username {options['username']!r}"
                raise CommandError(message) from exc
            emails.extend([profile.email, *(profile.emails or [])])

        emails = [e for e in emails if e]
        if not emails:
            message = "Provide at least one email address or --username"
            raise CommandError(message)

        up = UPExternalClientApp(client=self.get_client())
        summary = up.lookup(emails)

        if options["as_json"]:
            data = asdict(summary)
            data["contact"] = (
                summary.contact.model_dump() if summary.contact else None
            )
            self.emit_json(data)
            return

        self.stdout.write(f"Searched: {', '.join(emails)}")
        if not summary.found:
            self.stdout.write(self.style.WARNING("No contact found in UP"))
            return

        status = "eligible (active)" if summary.eligible else "not eligible"
        style = self.style.SUCCESS if summary.eligible else self.style.WARNING
        self.stdout.write(style(f"UP Commons membership: {status}"))
        self.stdout.write(f"  matched email  {summary.matched_email}")
        self.stdout.write(f"  contact        {summary.contact.Name}")
        self.stdout.write(f"  contact id     {summary.contact.Id}")
        self.stdout.write(f"  account id     {summary.account_id}")
        self.stdout.write(
            f"  current staff  {summary.contact.Current_Staff__c}"
        )
