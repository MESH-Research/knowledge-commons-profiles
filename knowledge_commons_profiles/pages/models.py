from django.db import models


class SitePage(models.Model):
    """
    A simple CMS-style page with configurable content.

    Pages are identified by their slug, which corresponds to the URL path.
    The title, body (HTML), and an optional call-to-action link are all
    editable via the Django admin.
    """

    slug = models.SlugField(
        max_length=200,
        unique=True,
        help_text="URL path identifier for this page (e.g. 'registration-start').",
    )
    title = models.CharField(
        max_length=300,
        help_text="Page title displayed in the heading and browser tab.",
    )
    body = models.TextField(
        help_text="HTML content for the page body.",
    )
    cta_url = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Optional call-to-action URL. Can be an absolute path "
            "(e.g. '/login/') or a full URL."
        ),
    )
    cta_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Text for the call-to-action button (if cta_url is set).",
    )

    class Meta:
        verbose_name = "Site Page"
        verbose_name_plural = "Site Pages"

    def __str__(self):
        return self.title
