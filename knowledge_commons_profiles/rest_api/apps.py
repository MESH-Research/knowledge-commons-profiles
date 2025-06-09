from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RestAPIConfig(AppConfig):
    name = "knowledge_commons_profiles.rest_api"
    label = "rest_api"
    verbose_name = _("REST API")
