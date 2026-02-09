from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.pages.models import SitePage
from knowledge_commons_profiles.pages.views import site_page


class SitePageModelTests(TestCase):
    def test_str_returns_title(self):
        page = SitePage(title="Test Page", slug="test-page", body="<p>Hi</p>")
        self.assertEqual(str(page), "Test Page")


class SitePageViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.page = SitePage.objects.create(
            slug="test-slug",
            title="Test Title",
            body="<p>Test body content</p>",
            cta_url="/some-url/",
            cta_text="Click Here",
        )

    def test_existing_page_returns_200(self):
        request = self.factory.get("/test/")
        response = site_page(request, slug="test-slug")
        self.assertEqual(response.status_code, 200)

    def test_nonexistent_slug_returns_404(self):
        from django.http import Http404

        request = self.factory.get("/test/")
        with self.assertRaises(Http404):
            site_page(request, slug="nonexistent")

    def test_page_title_in_response(self):
        request = self.factory.get("/test/")
        response = site_page(request, slug="test-slug")
        content = response.content.decode()
        self.assertIn("Test Title", content)

    def test_page_body_rendered_as_html(self):
        request = self.factory.get("/test/")
        response = site_page(request, slug="test-slug")
        content = response.content.decode()
        self.assertIn("<p>Test body content</p>", content)

    def test_cta_button_rendered_when_url_set(self):
        request = self.factory.get("/test/")
        response = site_page(request, slug="test-slug")
        content = response.content.decode()
        self.assertIn('href="/some-url/"', content)
        self.assertIn("Click Here", content)

    def test_cta_button_not_rendered_when_url_empty(self):
        self.page.cta_url = ""
        self.page.save()
        request = self.factory.get("/test/")
        response = site_page(request, slug="test-slug")
        content = response.content.decode()
        self.assertNotIn("btn-primary", content)


class TermsOfServicePageTests(TestCase):
    def setUp(self):
        self.page, _ = SitePage.objects.update_or_create(
            slug="terms-of-service",
            defaults={
                "title": "Terms of Service",
                "body": "<p>These are the terms.</p>",
            },
        )

    def test_terms_page_can_be_retrieved_by_slug(self):
        page = SitePage.objects.get(slug="terms-of-service")
        self.assertEqual(page.title, "Terms of Service")
        self.assertEqual(page.body, "<p>These are the terms.</p>")

    def test_str_returns_title(self):
        self.assertEqual(str(self.page), "Terms of Service")


class RegistrationStartPageTests(TestCase):
    def setUp(self):
        self.page, _ = SitePage.objects.update_or_create(
            slug="registration-start",
            defaults={
                "title": "Create Your Account",
                "body": (
                    "<p>To create your Knowledge Commons account, you will "
                    "first sign in through your institution or an identity "
                    "provider.</p>"
                ),
                "cta_url": "/login/",
                "cta_text": "Begin Registration",
            },
        )

    def test_registration_start_url_resolves(self):
        url = reverse("registration_start")
        self.assertEqual(url, "/registration/start/")

    def test_registration_start_returns_200(self):
        response = self.client.get("/registration/start/")
        self.assertEqual(response.status_code, 200)

    def test_registration_start_contains_title(self):
        response = self.client.get("/registration/start/")
        self.assertContains(response, "Create Your Account")

    def test_registration_start_contains_cta_link(self):
        response = self.client.get("/registration/start/")
        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, "Begin Registration")

    def test_registration_start_body_is_configurable(self):
        self.page.body = "<p>Custom content here.</p>"
        self.page.save()
        response = self.client.get("/registration/start/")
        self.assertContains(response, "Custom content here.")

    def test_registration_start_returns_404_if_page_deleted(self):
        self.page.delete()
        response = self.client.get("/registration/start/")
        self.assertEqual(response.status_code, 404)
