from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CILogonConfig(AppConfig):
    name = "knowledge_commons_profiles.cilogon"
    label = "cilogon"
    verbose_name = _("CILogon")
