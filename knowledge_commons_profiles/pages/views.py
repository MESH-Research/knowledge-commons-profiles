from django.http import Http404
from django.shortcuts import render

from knowledge_commons_profiles.pages.models import SitePage


def site_page(request, slug):
    """
    Render a SitePage looked up by its slug.

    Raises Http404 if no page with the given slug exists.
    """
    try:
        page = SitePage.objects.get(slug=slug)
    except SitePage.DoesNotExist:
        raise Http404("Page not found.")

    return render(request, "pages/site_page.html", {"page": page})
