"""
Tests for input validation in views.py
"""

from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase

from knowledge_commons_profiles.cilogon.views import _contains_html_or_script
from knowledge_commons_profiles.cilogon.views import register
from knowledge_commons_profiles.cilogon.views import sanitize_full_name
from knowledge_commons_profiles.cilogon.views import validate_form


class TestContainsHtmlOrScript(TestCase):
    """Tests for the _contains_html_or_script helper function"""

    def test_empty_string_returns_false(self):
        self.assertFalse(_contains_html_or_script(""))

    def test_none_returns_false(self):
        self.assertFalse(_contains_html_or_script(None))

    def test_plain_text_returns_false(self):
        self.assertFalse(_contains_html_or_script("John Doe"))

    def test_text_with_special_chars_returns_false(self):
        self.assertFalse(_contains_html_or_script("John O'Brien-Smith"))
        self.assertFalse(_contains_html_or_script("José García"))
        self.assertFalse(_contains_html_or_script("François Müller"))

    def test_html_script_tag_returns_true(self):
        self.assertTrue(_contains_html_or_script("<script>alert('xss')</script>"))

    def test_html_img_tag_returns_true(self):
        self.assertTrue(
            _contains_html_or_script('<img src="x" onerror="alert(1)">')
        )

    def test_html_div_tag_returns_true(self):
        self.assertTrue(_contains_html_or_script("<div>content</div>"))

    def test_self_closing_tag_returns_true(self):
        self.assertTrue(_contains_html_or_script("<br/>"))

    def test_javascript_protocol_returns_true(self):
        self.assertTrue(_contains_html_or_script("javascript:alert(1)"))

    def test_javascript_protocol_case_insensitive(self):
        self.assertTrue(_contains_html_or_script("JAVASCRIPT:alert(1)"))
        self.assertTrue(_contains_html_or_script("JavaScript:void(0)"))

    def test_onclick_handler_returns_true(self):
        self.assertTrue(_contains_html_or_script('onclick="alert(1)"'))
        self.assertTrue(_contains_html_or_script("onclick = alert(1)"))

    def test_onerror_handler_returns_true(self):
        self.assertTrue(_contains_html_or_script('onerror="alert(1)"'))

    def test_onload_handler_returns_true(self):
        self.assertTrue(_contains_html_or_script("onload=malicious()"))

    def test_data_uri_returns_true(self):
        self.assertTrue(_contains_html_or_script("data:text/html,<script>"))

    def test_vbscript_protocol_returns_true(self):
        self.assertTrue(_contains_html_or_script("vbscript:msgbox(1)"))


class TestSanitizeFullName(TestCase):
    """Tests for the sanitize_full_name helper function"""

    def test_empty_string_returns_empty(self):
        self.assertEqual(sanitize_full_name(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(sanitize_full_name(None), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(sanitize_full_name("John Doe"), "John Doe")

    def test_strips_whitespace(self):
        self.assertEqual(sanitize_full_name("  John Doe  "), "John Doe")

    def test_escapes_html_entities(self):
        self.assertEqual(sanitize_full_name("<script>"), "&lt;script&gt;")
        self.assertEqual(
            sanitize_full_name("<b>bold</b>"), "&lt;b&gt;bold&lt;/b&gt;"
        )

    def test_escapes_ampersand(self):
        self.assertEqual(sanitize_full_name("Tom & Jerry"), "Tom &amp; Jerry")

    def test_escapes_quotes(self):
        result = sanitize_full_name('Say "hello"')
        self.assertEqual(result, "Say &quot;hello&quot;")

    def test_truncates_long_names(self):
        long_name = "A" * 150
        result = sanitize_full_name(long_name)
        self.assertEqual(len(result), 100)

    def test_special_characters_preserved(self):
        self.assertEqual(sanitize_full_name("José García"), "José García")
        result = sanitize_full_name("François Müller")
        self.assertEqual(result, "François Müller")


class TestValidateForm(TestCase):
    """Tests for the validate_form function"""

    def setUp(self):
        self.factory = RequestFactory()

    def _create_request(self):
        request = self.factory.post("/register/")
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        # Enable messages framework
        from django.contrib.messages.storage.session import SessionStorage

        request._messages = SessionStorage(request)
        return request

    def _get_messages(self, request):
        return [str(m) for m in get_messages(request)]

    # Tests for empty field validation
    def test_empty_email_returns_error(self):
        request = self._create_request()
        result = validate_form("", "John Doe", request, "johndoe")
        self.assertTrue(result)
        self.assertIn("Please fill in all fields", self._get_messages(request))

    def test_empty_username_returns_error(self):
        request = self._create_request()
        result = validate_form("john@example.com", "John Doe", request, "")
        self.assertTrue(result)
        self.assertIn("Please fill in all fields", self._get_messages(request))

    def test_empty_full_name_returns_error(self):
        request = self._create_request()
        result = validate_form("john@example.com", "", request, "johndoe")
        self.assertTrue(result)
        self.assertIn("Please fill in all fields", self._get_messages(request))

    def test_none_values_return_error(self):
        request = self._create_request()
        result = validate_form(None, None, request, None)
        self.assertTrue(result)
        self.assertIn("Please fill in all fields", self._get_messages(request))

    # Tests for email validation
    def test_valid_email_passes(self):
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "johndoe")
        messages = self._get_messages(request)
        self.assertNotIn("Please enter a valid email address", messages)

    def test_invalid_email_no_at_symbol(self):
        request = self._create_request()
        result = validate_form("invalid-email", "John Doe", request, "johndoe")
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("Please enter a valid email address", messages)

    def test_invalid_email_no_domain(self):
        request = self._create_request()
        result = validate_form("john@", "John Doe", request, "johndoe")
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("Please enter a valid email address", messages)

    def test_invalid_email_spaces(self):
        request = self._create_request()
        result = validate_form(
            "john doe@example.com", "John Doe", request, "johndoe"
        )
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("Please enter a valid email address", messages)

    def test_invalid_email_multiple_at_symbols(self):
        request = self._create_request()
        result = validate_form("john@@example.com", "John Doe", request, "jdoe")
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("Please enter a valid email address", messages)

    # Tests for username validation
    def test_valid_username_alphanumeric(self):
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "johndoe123")
        messages = self._get_messages(request)
        self.assertNotIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )

    def test_valid_username_with_underscore(self):
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "john_doe")
        messages = self._get_messages(request)
        self.assertNotIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )

    def test_valid_username_with_hyphen(self):
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "john-doe")
        messages = self._get_messages(request)
        self.assertNotIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )

    def test_username_too_short(self):
        request = self._create_request()
        result = validate_form("john@example.com", "John Doe", request, "ab")
        self.assertTrue(result)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            self._get_messages(request),
        )

    def test_username_too_long(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "a" * 31
        )
        self.assertTrue(result)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            self._get_messages(request),
        )

    def test_username_with_spaces_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "john d"
        )
        self.assertTrue(result)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            self._get_messages(request),
        )

    def test_username_with_special_chars_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "john@d"
        )
        self.assertTrue(result)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            self._get_messages(request),
        )

    def test_username_with_period_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "john.d"
        )
        self.assertTrue(result)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            self._get_messages(request),
        )

    def test_username_with_html_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "<script>"
        )
        self.assertTrue(result)

    # Tests for full name validation
    def test_full_name_normal_passes(self):
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "johndoe")
        messages = self._get_messages(request)
        self.assertNotIn("Full name must be 100 characters or less", messages)
        self.assertNotIn(
            "Full name contains invalid characters or formatting", messages
        )

    def test_full_name_too_long(self):
        request = self._create_request()
        long_name = "A" * 101
        result = validate_form(
            "john@example.com", long_name, request, "johndoe"
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name must be 100 characters or less",
            self._get_messages(request),
        )

    def test_full_name_with_script_tag_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com",
            "<script>alert('xss')</script>",
            request,
            "johndoe",
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name contains invalid characters or formatting",
            self._get_messages(request),
        )

    def test_full_name_with_img_tag_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com",
            '<img src="x" onerror="alert(1)">',
            request,
            "johndoe",
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name contains invalid characters or formatting",
            self._get_messages(request),
        )

    def test_full_name_with_javascript_protocol_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com",
            "javascript:alert(1)",
            request,
            "johndoe",
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name contains invalid characters or formatting",
            self._get_messages(request),
        )

    def test_full_name_with_onclick_rejected(self):
        request = self._create_request()
        result = validate_form(
            "john@example.com",
            'test onclick="alert(1)"',
            request,
            "johndoe",
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name contains invalid characters or formatting",
            self._get_messages(request),
        )

    def test_full_name_with_special_chars_allowed(self):
        request = self._create_request()
        validate_form(
            "john@example.com", "José García-Müller", request, "johndoe"
        )
        messages = self._get_messages(request)
        self.assertNotIn(
            "Full name contains invalid characters or formatting", messages
        )

    def test_full_name_with_apostrophe_allowed(self):
        request = self._create_request()
        validate_form("john@example.com", "John O'Brien", request, "johndoe")
        messages = self._get_messages(request)
        self.assertNotIn(
            "Full name contains invalid characters or formatting", messages
        )

    # Tests for existing email/username checks
    @patch("knowledge_commons_profiles.cilogon.views.Profile.objects.filter")
    def test_existing_email_returns_error(self, mock_filter):
        # First call (email check) returns a profile
        # Subsequent calls return None
        mock_profile = MagicMock()
        mock_filter.return_value.first.side_effect = [
            mock_profile,
            None,
            None,
        ]

        request = self._create_request()
        result = validate_form(
            "existing@example.com", "John Doe", request, "johndoe"
        )
        self.assertTrue(result)
        self.assertIn("This email already exists", self._get_messages(request))

    @patch("knowledge_commons_profiles.cilogon.views.Profile.objects.filter")
    def test_existing_username_returns_error(self, mock_filter):
        # Email checks return None, username check returns a profile
        mock_profile = MagicMock()
        mock_filter.return_value.first.side_effect = [None, None, mock_profile]

        request = self._create_request()
        result = validate_form(
            "john@example.com", "John Doe", request, "existing_user"
        )
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("This username already exists", messages)

    # Test multiple validation errors
    def test_multiple_errors_collected(self):
        request = self._create_request()
        result = validate_form(
            "invalid-email",  # Invalid email
            "<script>hack</script>",  # XSS attempt
            request,
            "a",  # Too short username
        )
        self.assertTrue(result)
        messages = self._get_messages(request)
        self.assertIn("Please enter a valid email address", messages)
        self.assertIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )
        self.assertIn(
            "Full name contains invalid characters or formatting", messages
        )


class TestValidateFormEdgeCases(TestCase):
    """Edge case tests for input validation"""

    def setUp(self):
        self.factory = RequestFactory()

    def _create_request(self):
        request = self.factory.post("/register/")
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        from django.contrib.messages.storage.session import SessionStorage

        request._messages = SessionStorage(request)
        return request

    def _get_messages(self, request):
        return [str(m) for m in get_messages(request)]

    def test_username_boundary_3_chars(self):
        """Username with exactly 3 characters should be valid"""
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "abc")
        messages = self._get_messages(request)
        self.assertNotIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )

    def test_username_boundary_30_chars(self):
        """Username with exactly 30 characters should be valid"""
        request = self._create_request()
        validate_form("john@example.com", "John Doe", request, "a" * 30)
        messages = self._get_messages(request)
        self.assertNotIn(
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
            messages,
        )

    def test_full_name_boundary_100_chars(self):
        """Full name with exactly 100 characters should be valid"""
        request = self._create_request()
        validate_form("john@example.com", "A" * 100, request, "johndoe")
        messages = self._get_messages(request)
        self.assertNotIn("Full name must be 100 characters or less", messages)

    def test_email_with_plus_sign(self):
        """Email addresses with + sign should be valid"""
        request = self._create_request()
        validate_form("john+tag@example.com", "John Doe", request, "johndoe")
        messages = self._get_messages(request)
        self.assertNotIn("Please enter a valid email address", messages)

    def test_email_with_subdomain(self):
        """Email addresses with subdomains should be valid"""
        request = self._create_request()
        validate_form(
            "john@mail.example.com", "John Doe", request, "johndoe"
        )
        messages = self._get_messages(request)
        self.assertNotIn("Please enter a valid email address", messages)

    def test_full_name_unicode(self):
        """Full names with Unicode characters should be valid"""
        request = self._create_request()
        validate_form(
            "john@example.com", "Zoë Björk-Günther", request, "johndoe"
        )
        messages = self._get_messages(request)
        self.assertNotIn(
            "Full name contains invalid characters or formatting", messages
        )

    def test_mixed_case_xss_pattern(self):
        """XSS patterns should be detected regardless of case"""
        request = self._create_request()
        result = validate_form(
            "john@example.com",
            'OnClIcK="alert(1)"',
            request,
            "johndoe",
        )
        self.assertTrue(result)
        self.assertIn(
            "Full name contains invalid characters or formatting",
            self._get_messages(request),
        )


class TestAcceptTermsValidation(TestCase):
    """Tests for the accept_terms checkbox validation in the register view"""

    def setUp(self):
        self.factory = RequestFactory()

    def _create_post_request(self, data):
        request = self.factory.post("/register/", data=data)
        middleware = SessionMiddleware(get_response=MagicMock())
        middleware.process_request(request)
        request.session.save()
        from django.contrib.messages.storage.session import SessionStorage

        request._messages = SessionStorage(request)
        # Simulate an anonymous user
        request.user = MagicMock()
        request.user.is_authenticated = False
        return request

    def _get_messages(self, request):
        return [str(m) for m in get_messages(request)]

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
        return_value=(True, {"sub": "test-sub-123", "email": "t@example.com"}),
    )
    def test_missing_accept_terms_shows_error(self, mock_userinfo):
        """Submitting without accept_terms produces an error message"""
        request = self._create_post_request(
            {
                "username": "newuser",
                "full_name": "New User",
                "email": "newuser@example.com",
            }
        )
        register(request)
        msgs = self._get_messages(request)
        self.assertIn("You must accept the terms and conditions", msgs)

    @patch(
        "knowledge_commons_profiles.cilogon.views.get_secure_userinfo",
        return_value=(True, {"sub": "test-sub-123", "email": "t@example.com"}),
    )
    def test_accept_terms_present_no_error(self, mock_userinfo):
        """Submitting with accept_terms does not produce the terms error"""
        request = self._create_post_request(
            {
                "username": "newuser",
                "full_name": "New User",
                "email": "newuser@example.com",
                "accept_terms": "on",
            }
        )
        register(request)
        msgs = self._get_messages(request)
        self.assertNotIn("You must accept the terms and conditions", msgs)
