"""
Run an ad-hoc SOQL query with the External Client App token.
"""

import json

from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)

DEFAULT_SOQL = "SELECT Id, Name, Email, AccountId FROM Contact LIMIT 5"


class Command(UPSalesforceCommand):
    help = "Run a SOQL query against UP Salesforce and print the records"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "soql",
            nargs="?",
            default=DEFAULT_SOQL,
            help=f"The SOQL to run (default: {DEFAULT_SOQL})",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="fetch_all",
            help="Follow nextRecordsUrl and fetch every page",
        )

    def run(self, *args, **options):
        client = self.get_client()

        if options["fetch_all"]:
            records = client.query_all(options["soql"])
            result = {
                "totalSize": len(records),
                "done": True,
                "records": records,
            }
        else:
            result = client.query(options["soql"])

        if options["as_json"]:
            self.emit_json(result)
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"{result.get('totalSize', 0)} record(s) "
                f"(done={result.get('done')})"
            )
        )
        for record in result.get("records", []):
            cleaned = {k: v for k, v in record.items() if k != "attributes"}
            self.stdout.write("  " + json.dumps(cleaned, default=str))
