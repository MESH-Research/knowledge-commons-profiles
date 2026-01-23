from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PagesConfig(AppConfig):
    name = "knowledge_commons_profiles.pages"
    label = "pages"
    verbose_name = _("Site Pages")
