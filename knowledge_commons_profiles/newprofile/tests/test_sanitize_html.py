"""
Tests for the sanitize_html utility function.

The allowlist deliberately matches the editor toolbar (bold, italic,
links, anchors) per issue #540 — anything else is stripped so users
don't see formatting silently disappear after save.
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

    def test_preserves_paragraph_tag(self):
        """Paragraphs are kept so editor content has structure."""
        html = "<p>Paragraph</p>"
        result = sanitize_html(html)
        self.assertIn("<p>", result)
        self.assertIn("Paragraph", result)

    def test_preserves_emphasis_tags(self):
        """em, strong, b, i tags should be preserved (the toolbar
        emits em/strong; b/i covered for pasted content)."""
        html = "<em>italic</em> <strong>bold</strong> <b>b</b> <i>i</i>"
        result = sanitize_html(html)
        self.assertIn("<em>italic</em>", result)
        self.assertIn("<strong>bold</strong>", result)
        self.assertIn("<b>b</b>", result)
        self.assertIn("<i>i</i>", result)

    def test_preserves_links_with_attributes(self):
        """Anchor tags with href and title attributes should be preserved."""
        html = '<a href="http://example.com" title="Example">link</a>'
        result = sanitize_html(html)
        self.assertIn('href="http://example.com"', result)
        self.assertIn("link", result)

    def test_preserves_anchor_id(self):
        """In-page anchors (TinyMCE 5+ uses id) should be preserved."""
        html = '<a id="bookmark">section</a>'
        result = sanitize_html(html)
        self.assertIn('id="bookmark"', result)
        self.assertIn("section", result)

    def test_preserves_anchor_name(self):
        """Legacy named anchors should be preserved for back-compat
        with content authored before TinyMCE 5."""
        html = '<a name="bookmark">section</a>'
        result = sanitize_html(html)
        self.assertIn('name="bookmark"', result)
        self.assertIn("section", result)

    def test_strips_disallowed_attributes_from_links(self):
        """Attributes not in the allowlist should be removed."""
        html = '<a href="http://example.com" onclick="alert(1)">link</a>'
        result = sanitize_html(html)
        self.assertNotIn("onclick", result)
        self.assertIn("href", result)

    def test_strips_underline_preserves_text(self):
        """Underline isn't in the toolbar (issue #540) so the tag is
        stripped on save; the text survives."""
        html = "<u>underlined text</u>"
        result = sanitize_html(html)
        self.assertNotIn("<u>", result)
        self.assertNotIn("</u>", result)
        self.assertIn("underlined text", result)

    def test_strips_text_alignment_style(self):
        """Alignment via style attribute is removed (issue #540)."""
        html = '<p style="text-align: center">centred</p>'
        result = sanitize_html(html)
        self.assertNotIn("text-align", result)
        self.assertNotIn("style=", result)
        self.assertIn("<p>", result)
        self.assertIn("centred", result)

    def test_strips_align_attribute(self):
        """Legacy align attribute is removed (issue #540)."""
        html = '<p align="center">centred</p>'
        result = sanitize_html(html)
        self.assertNotIn("align=", result)
        self.assertIn("<p>", result)
        self.assertIn("centred", result)

    def test_strips_color_via_font_tag(self):
        """Font tags (with color) are stripped entirely (issue #540)."""
        html = '<font color="red">red text</font>'
        result = sanitize_html(html)
        self.assertNotIn("<font", result)
        self.assertNotIn("color=", result)
        self.assertIn("red text", result)

    def test_strips_color_via_style_attribute(self):
        """Inline color styles are stripped (issue #540)."""
        html = '<p style="color: red">red text</p>'
        result = sanitize_html(html)
        self.assertNotIn("color:", result)
        self.assertNotIn("style=", result)
        self.assertIn("<p>", result)
        self.assertIn("red text", result)

    def test_strips_lists_preserves_text(self):
        """List tags aren't in the toolbar — text content survives."""
        html = "<ul><li>item one</li><li>item two</li></ul>"
        result = sanitize_html(html)
        self.assertNotIn("<ul>", result)
        self.assertNotIn("<ol>", result)
        self.assertNotIn("<li>", result)
        self.assertIn("item one", result)
        self.assertIn("item two", result)

    def test_strips_headings_preserves_text(self):
        """Heading tags aren't in the toolbar — text content survives."""
        html = "<h1>Title</h1><h3>Subtitle</h3>"
        result = sanitize_html(html)
        for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.assertNotIn(f"<{tag}>", result)
            self.assertNotIn(f"</{tag}>", result)
        self.assertIn("Title", result)
        self.assertIn("Subtitle", result)

    def test_strips_tables_preserves_text(self):
        """Table tags aren't in the toolbar — text content survives."""
        html = (
            "<table><thead><tr><th>H</th></tr></thead>"
            "<tbody><tr><td>D</td></tr></tbody></table>"
        )
        result = sanitize_html(html)
        for tag in ("table", "thead", "tbody", "tr", "th", "td"):
            self.assertNotIn(f"<{tag}>", result)
        self.assertIn("H", result)
        self.assertIn("D", result)

    def test_strips_img_tags(self):
        """Images aren't in the toolbar — img tags are removed."""
        html = '<img src="photo.jpg" alt="Photo" width="100" height="100">'
        result = sanitize_html(html)
        self.assertNotIn("<img", result)
        self.assertNotIn("src=", result)

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

    def test_preserves_br_tags(self):
        """br tags should be preserved (Shift+Enter line breaks)."""
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
