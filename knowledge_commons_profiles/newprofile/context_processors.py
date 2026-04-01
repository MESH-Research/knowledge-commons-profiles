"""
Context processors
"""

import time
from urllib.parse import urlparse
from urllib.parse import urlunparse

from django.conf import settings


def cc_search(request):
    return {"CC_SEARCH_URL": settings.CC_SEARCH_URL}


def _rewrite_domain(url, default_domain, target_domain):
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname or hostname != default_domain:
        return url
    new_netloc = target_domain
    if parsed.port:
        new_netloc = f"{target_domain}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def nav_links(request):
    urls = {
        "NAV_NEWS_FEED_URL": settings.NAV_NEWS_FEED_URL,
        "NAV_GROUPS_URL": settings.NAV_GROUPS_URL,
        "NAV_SITES_URL": settings.NAV_SITES_URL,
        "NAV_WORKS_URL": settings.NAV_WORKS_URL,
        "NAV_SUPPORT_URL": settings.NAV_SUPPORT_URL,
        "NAV_ORGANIZATIONS_URL": settings.NAV_ORGANIZATIONS_URL,
        "NAV_ABOUT_URL": settings.NAV_ABOUT_URL,
        "NAV_BLOG_URL": settings.NAV_BLOG_URL,
    }

    session = getattr(request, "session", {})
    network_domain = session.get("nav_network_domain")
    if not network_domain:
        return urls

    ts = session.get("nav_network_domain_ts", 0)
    timeout = getattr(settings, "NAV_NETWORK_SESSION_TIMEOUT", 3600)
    if time.time() - ts > timeout:
        session.pop("nav_network_domain", None)
        session.pop("nav_network_domain_ts", None)
        return urls

    default_domain = getattr(settings, "NAV_DEFAULT_DOMAIN", "hcommons.org")
    return {
        key: _rewrite_domain(url, default_domain, network_domain)
        for key, url in urls.items()
    }
