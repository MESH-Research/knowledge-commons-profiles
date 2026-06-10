# tests for the /works/ redirect route
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse


@override_settings(NAV_WORKS_URL="https://works.example.org/")
class GoToWorksTests(TestCase):
    def test_works_url_reverses_to_expected_path(self):
        self.assertEqual(reverse("go_to_works"), "/works/")

    def test_works_redirects_to_nav_works_url(self):
        response = self.client.get("/works/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://works.example.org/")
