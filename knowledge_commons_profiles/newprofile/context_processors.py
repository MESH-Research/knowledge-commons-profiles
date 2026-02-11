"""
Context processors
"""

from django.conf import settings


def cc_search(request):
    return {"CC_SEARCH_URL": settings.CC_SEARCH_URL}


def nav_links(request):
    return {
        "NAV_NEWS_FEED_URL": settings.NAV_NEWS_FEED_URL,
        "NAV_GROUPS_URL": settings.NAV_GROUPS_URL,
        "NAV_SITES_URL": settings.NAV_SITES_URL,
        "NAV_WORKS_URL": settings.NAV_WORKS_URL,
        "NAV_SUPPORT_URL": settings.NAV_SUPPORT_URL,
        "NAV_ORGANIZATIONS_URL": settings.NAV_ORGANIZATIONS_URL,
        "NAV_ABOUT_URL": settings.NAV_ABOUT_URL,
        "NAV_BLOG_URL": settings.NAV_BLOG_URL,
    }
