from django.test import SimpleTestCase
from django.utils.module_loading import import_string

from knowledge_commons_profiles.cilogon.admin_site import CustomAdminSite
from knowledge_commons_profiles.newprofile.apps import CustomAdminConfig


class CustomAdminConfigTests(SimpleTestCase):
    def test_default_site_is_fully_qualified_and_resolves(self):
        self.assertEqual(
            CustomAdminConfig.default_site,
            "knowledge_commons_profiles.cilogon.admin_site.CustomAdminSite",
        )
        self.assertIs(
            import_string(CustomAdminConfig.default_site), CustomAdminSite
        )
