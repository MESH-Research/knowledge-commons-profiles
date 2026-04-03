"""
Tests for the sanitize_html utility function.
"""

from django.test import TestCase

from knowledge_commons_profiles.newprofile.utils import sanitize_html


class SanitizeHtmlTests(TestCase):
    """Test HTML sanitization for profile content."""

    def test_strips_span_tags_preserves_text(self):
        """Span tags should be removed but their text content kept."""
        html = "<span>Hello world</span>"
        result = sanitize_html(html)
        self.assertNotIn("<span>", result)
        self.assertNotIn("</span>", result)
        self.assertIn("Hello world", result)

    def test_preserves_allowed_tags(self):
        """Tags in the allowlist should remain intact."""
        html = "<p>Paragraph</p>"
        result = sanitize_html(html)
        self.assertIn("<p>", result)
        self.assertIn("Paragraph", result)

    def test_preserves_emphasis_tags(self):
        """em, strong, b, i, u tags should be preserved."""
        html = "<em>italic</em> <strong>bold</strong> <b>b</b> <i>i</i>"
        result = sanitize_html(html)
        self.assertIn("<em>italic</em>", result)
        self.assertIn("<strong>bold</strong>", result)

    def test_preserves_links_with_attributes(self):
        """Anchor tags with href and title attributes should be preserved."""
        html = '<a href="http://example.com" title="Example">link</a>'
        result = sanitize_html(html)
        self.assertIn('href="http://example.com"', result)
        self.assertIn("link", result)

    def test_strips_disallowed_attributes_from_links(self):
        """Attributes not in the allowlist should be removed."""
        html = '<a href="http://example.com" onclick="alert(1)">link</a>'
        result = sanitize_html(html)
        self.assertNotIn("onclick", result)
        self.assertIn("href", result)

    def test_preserves_lists(self):
        """ul, ol, li tags should be preserved."""
        html = "<ul><li>item</li></ul>"
        result = sanitize_html(html)
        self.assertIn("<ul>", result)
        self.assertIn("<li>item</li>", result)

    def test_preserves_headings(self):
        """h1-h6 tags should be preserved."""
        html = "<h1>Title</h1><h3>Subtitle</h3>"
        result = sanitize_html(html)
        self.assertIn("<h1>Title</h1>", result)
        self.assertIn("<h3>Subtitle</h3>", result)

    def test_preserves_table_tags(self):
        """Table-related tags should be preserved."""
        html = (
            "<table><thead><tr><th>H</th></tr></thead>"
            "<tbody><tr><td>D</td></tr></tbody></table>"
        )
        result = sanitize_html(html)
        self.assertIn("<table>", result)
        self.assertIn("<td>D</td>", result)

    def test_strips_script_tags(self):
        """Script tags should be stripped (text content remains but is
        rendered harmless since the tag itself is removed)."""
        html = "<p>Safe</p><script>alert('xss')</script>"
        result = sanitize_html(html)
        self.assertNotIn("<script>", result)
        self.assertIn("Safe", result)

    def test_strips_style_tags(self):
        """Style tags and their content should be removed."""
        html = "<p>Content</p><style>body{color:red}</style>"
        result = sanitize_html(html)
        self.assertNotIn("<style>", result)

    def test_strips_div_tags_preserves_text(self):
        """Div tags should be stripped but text preserved."""
        html = "<div>Some text</div>"
        result = sanitize_html(html)
        self.assertNotIn("<div>", result)
        self.assertIn("Some text", result)

    def test_none_input_returns_none(self):
        """None input should return None."""
        result = sanitize_html(None)
        self.assertIsNone(result)

    def test_empty_string_returns_empty(self):
        """Empty string input should return empty string."""
        result = sanitize_html("")
        self.assertEqual(result, "")

    def test_real_world_span_example(self):
        """Test with the actual example from the bug report (issue #508)."""
        html = (
            "<span>Jack W. Chen works on early and medieval Chinese "
            "literature and thought.</span> The Poetics of Sovereignty "
            "<span>(2010) and </span>Anecdote, Network"
        )
        result = sanitize_html(html)
        self.assertNotIn("<span>", result)
        self.assertNotIn("</span>", result)
        self.assertIn(
            "Jack W. Chen works on early and medieval Chinese", result
        )
        self.assertIn("The Poetics of Sovereignty", result)
        self.assertIn("(2010) and", result)

    def test_preserves_img_with_allowed_attributes(self):
        """Img tags with allowed attributes should be preserved."""
        html = '<img src="photo.jpg" alt="Photo" width="100" height="100">'
        result = sanitize_html(html)
        self.assertIn("src=", result)
        self.assertIn("alt=", result)

    def test_preserves_br_tags(self):
        """br tags should be preserved."""
        html = "Line one<br>Line two"
        result = sanitize_html(html)
        self.assertIn("<br>", result)

    def test_linkifies_urls(self):
        """Bare URLs should be converted to clickable links."""
        html = "<p>Visit http://example.com for info</p>"
        result = sanitize_html(html)
        self.assertIn('<a href="http://example.com"', result)

    def test_nested_disallowed_tags_stripped(self):
        """Nested disallowed tags should all be stripped."""
        html = "<div><span><font>Text</font></span></div>"
        result = sanitize_html(html)
        self.assertNotIn("<div>", result)
        self.assertNotIn("<span>", result)
        self.assertNotIn("<font>", result)
        self.assertIn("Text", result)

    def test_escaped_span_entities_stripped(self):
        """HTML-escaped span entities like &lt;span&gt; should be unescaped
        and then stripped."""
        html = (
            "&lt;span&gt;Jack W. Chen works on literature."
            "&lt;/span&gt; <em>The Poetics</em>"
        )
        result = sanitize_html(html)
        self.assertNotIn("&lt;span&gt;", result)
        self.assertNotIn("&lt;/span&gt;", result)
        self.assertNotIn("<span>", result)
        self.assertIn("Jack W. Chen works on literature.", result)
        self.assertIn("<em>The Poetics</em>", result)

    def test_escaped_entities_mixed_with_real_tags(self):
        """Mix of escaped entities and real tags (as seen in production)."""
        html = (
            "&lt;span&gt;(2010) and&nbsp;&lt;/span&gt;"
            "<em>Anecdote, Network</em>"
        )
        result = sanitize_html(html)
        self.assertNotIn("&lt;span&gt;", result)
        self.assertNotIn("<span>", result)
        self.assertIn("(2010) and", result)
        self.assertIn("<em>Anecdote, Network</em>", result)

    def test_escaped_allowed_tags_preserved(self):
        """Escaped allowed tags should be unescaped and preserved."""
        html = "&lt;em&gt;italic&lt;/em&gt;"
        result = sanitize_html(html)
        self.assertIn("<em>italic</em>", result)
