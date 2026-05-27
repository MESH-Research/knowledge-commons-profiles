from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig
from django.utils.translation import gettext_lazy as _


class CustomAdminConfig(AdminConfig):
    default_site = "cilogon.admin_site.CustomAdminSite"


class NewProfileConfig(AppConfig):
    name = "knowledge_commons_profiles.newprofile"
    label = "newprofile"
    verbose_name = _("Profiles")

    def ready(self):
        """
        Import signal handlers when the app is ready.

        This method is called when Django starts up. It imports the signals
        module to register all signal handlers for the Profile model.
        """
        # Import signals to register them
        # ruff: noqa: F401
        import knowledge_commons_profiles.newprofile.signals
