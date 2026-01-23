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
    except SitePage.DoesNotExist as ex:
        msg = "Page not found."
        raise Http404(msg) from ex

    return render(request, "pages/site_page.html", {"page": page})
