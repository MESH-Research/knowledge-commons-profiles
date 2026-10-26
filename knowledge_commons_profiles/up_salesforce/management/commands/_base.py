"""
Shared plumbing for the ``up_eca_*`` management commands.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from knowledge_commons_profiles.up_salesforce.client import SalesforceRestClient
from knowledge_commons_profiles.up_salesforce.exceptions import (
    UPSalesforceError,
)


class UPSalesforceCommand(BaseCommand):
    """Base command: builds a client and turns API errors into CLI errors."""

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit machine-readable JSON instead of a summary",
        )

    def handle(self, *args, **options):
        try:
            return self.run(*args, **options)
        except UPSalesforceError as exc:
            raise CommandError(str(exc)) from exc

    def run(self, *args, **options):  # pragma: no cover - overridden
        raise NotImplementedError

    def get_client(self) -> SalesforceRestClient:
        return SalesforceRestClient()

    def emit_json(self, data) -> None:
        self.stdout.write(json.dumps(data, indent=2, default=str))
