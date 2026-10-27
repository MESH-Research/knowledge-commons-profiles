"""
Show the identity Salesforce associates with the External Client App token
(the app's configured "Run As" user).
"""

from knowledge_commons_profiles.up_salesforce.management.commands._base import (
    UPSalesforceCommand,
)

DISPLAY_FIELDS = (
    "user_id",
    "organization_id",
    "preferred_username",
    "name",
    "email",
    "user_type",
    "language",
    "locale",
    "timezone",
)


class Command(UPSalesforceCommand):
    help = (
        "Call the Salesforce userinfo endpoint with the External Client App "
        "token to show which user the integration runs as"
    )

    def run(self, *args, **options):
        info = self.get_client().userinfo()

        if options["as_json"]:
            self.emit_json(info)
            return

        self.stdout.write(self.style.SUCCESS("Authenticated to Salesforce as:"))
        for field in DISPLAY_FIELDS:
            if field in info:
                self.stdout.write(f"  {field:<19} {info[field]}")
