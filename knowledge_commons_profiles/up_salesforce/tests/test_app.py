from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class AppRegistrationTests(SimpleTestCase):
    def test_app_is_installed_with_expected_label(self):
        config = apps.get_app_config("up_salesforce")
        self.assertEqual(
            config.name, "knowledge_commons_profiles.up_salesforce"
        )

    def test_settings_exist_with_defaults(self):
        for name in (
            "UP_ECA_CONSUMER_KEY",
            "UP_ECA_CONSUMER_SECRET",
            "UP_ECA_LOGIN_URL",
            "UP_ECA_API_VERSION",
            "UP_ECA_TOKEN_CACHE_TIMEOUT",
            "UP_ECA_CACHE_TIMEOUT",
        ):
            self.assertTrue(hasattr(settings, name), name)
        self.assertTrue(settings.UP_ECA_LOGIN_URL.startswith("https://"))
        self.assertTrue(settings.UP_ECA_API_VERSION.startswith("v"))

    def test_legacy_up_settings_are_untouched(self):
        for name in (
            "UP_API_TOKEN",
            "UP_API_BASE_URL",
            "UP_CLIENT_ID",
            "UP_CLIENT_SECRET",
            "UP_REFRESH_TOKEN",
        ):
            self.assertTrue(hasattr(settings, name), name)
        self.assertIn(
            ("UP", ["Association of American University Presses"]),
            settings.EXTERNAL_SYNC_CLASSES,
        )
