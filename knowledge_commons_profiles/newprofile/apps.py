from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NewProfileConfig(AppConfig):
    name = "knowledge_commons_profiles.newprofile"
    label = "newprofile"
    verbose_name = _("Profiles")
