from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UPSalesforceConfig(AppConfig):
    """
    Salesforce sync for the Association of University Presses (UP) using
    an External Client App and the OAuth 2.0 client-credentials flow.

    This app is deliberately independent of ``cilogon.sync_apis.up`` so the
    legacy refresh-token integration keeps working untouched while the
    new credentials are rolled out.
    """

    name = "knowledge_commons_profiles.up_salesforce"
    label = "up_salesforce"
    verbose_name = _("UP Salesforce (External Client App)")
