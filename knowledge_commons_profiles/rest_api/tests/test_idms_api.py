import unittest

from pydantic import ValidationError

from knowledge_commons_profiles.rest_api.idms_api import APIClientConfig


class TestAPIClientConfigBaseURLScheme(unittest.TestCase):
    """Verify APIClientConfig normalises scheme-less base URLs.

    Regression: GitHub issue #529. A deployment env var
    (WORKS_UPDATE_ENDPOINTS) without an http(s):// scheme crashed the
    /activate/ view because pydantic's HttpUrl rejected the raw host.
    """

    def test_base_url_without_scheme_gets_https_prepended(self):
        config = APIClientConfig(base_url="works.hcommons-staging.org/")
        self.assertTrue(
            str(config.base_url).startswith("https://"),
            msg=f"expected https:// prefix, got {config.base_url!s}",
        )
        self.assertIn("works.hcommons-staging.org", str(config.base_url))

    def test_base_url_with_https_scheme_preserved(self):
        config = APIClientConfig(base_url="https://works.hcommons.org/")
        self.assertTrue(str(config.base_url).startswith("https://"))

    def test_base_url_with_http_scheme_preserved(self):
        config = APIClientConfig(base_url="http://localhost:8000/")
        url_str = str(config.base_url)
        self.assertTrue(url_str.startswith("http://"))
        self.assertFalse(url_str.startswith("https://"))

    def test_base_url_bare_host_no_trailing_slash(self):
        config = APIClientConfig(base_url="works.hcommons-staging.org")
        self.assertTrue(str(config.base_url).startswith("https://"))
        self.assertIn("works.hcommons-staging.org", str(config.base_url))

    def test_base_url_still_rejects_garbage(self):
        with self.assertRaises(ValidationError):
            APIClientConfig(base_url="not a url at all")
