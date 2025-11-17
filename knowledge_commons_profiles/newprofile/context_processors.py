"""
Context processors
"""

from django.conf import settings


def cc_search(request):
    return {"CC_SEARCH_URL": settings.CC_SEARCH_URL}
