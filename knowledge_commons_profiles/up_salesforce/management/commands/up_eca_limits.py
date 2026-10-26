"""
Show Salesforce org API limits as seen by the External Client App.
"""

from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)

HEADLINE_LIMITS = (
    "DailyApiRequests",
    "DailyBulkApiBatches",
    "DailyStreamingApiEvents",
    "ConcurrentAsyncGetReportInstances",
)


class Command(UPSalesforceCommand):
    help = (
        "Fetch the org's API limits with the External Client App token "
        "(a cheap end-to-end connectivity check)"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--all",
            action="store_true",
            dest="show_all",
            help="Print every limit rather than the headline ones",
        )

    def run(self, *args, **options):
        limits = self.get_client().limits()

        if options["as_json"]:
            self.emit_json(limits)
            return

        names = (
            sorted(limits)
            if options["show_all"]
            else [n for n in HEADLINE_LIMITS if n in limits]
        )
        self.stdout.write(self.style.SUCCESS("Salesforce API limits:"))
        for name in names:
            value = limits[name]
            if isinstance(value, dict) and "Max" in value:
                self.stdout.write(
                    f"  {name:<40} {value.get('Remaining')} / {value['Max']} "
                    f"remaining"
                )
            else:
                self.stdout.write(f"  {name:<40} {value}")
