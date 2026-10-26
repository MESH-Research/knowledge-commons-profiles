"""
Obtain an access token from Salesforce with the External Client App
credentials and show (a masked form of) the result.
"""

from knowledge_commons_profiles.up_salesforce.auth import (
    ClientCredentialsTokenProvider,
)
from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)


class Command(UPSalesforceCommand):
    help = (
        "Request a client-credentials access token from the UP Salesforce "
        "External Client App and print its details (token masked)"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Ignore any cached token and request a new one",
        )

    def run(self, *args, **options):
        provider = ClientCredentialsTokenProvider()
        cached = None if options["refresh"] else provider.peek_cached()
        source = "cache" if cached else "fresh"
        token = cached or provider.get_token(force_refresh=options["refresh"])

        data = {
            "source": source,
            "token_url": provider.token_url,
            "instance_url": token.instance_url,
            "token_type": token.token_type,
            "access_token": token.masked_token(),
            "issued_at": token.issued_at_datetime,
            "scope": token.scope,
            "id": token.id,
        }

        if options["as_json"]:
            self.emit_json(data)
            return

        self.stdout.write(
            self.style.SUCCESS(f"Access token obtained ({source})")
        )
        for key, value in data.items():
            if key == "source":
                continue
            self.stdout.write(f"  {key:<13} {value}")
