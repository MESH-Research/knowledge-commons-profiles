"""
Context processors
"""

from urllib.parse import urlparse
from urllib.parse import urlunparse

from django.conf import settings

from knowledge_commons_profiles.newprofile.network_urls import network_domain


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


# Nav links that follow the network context (the community surfaces on
# the network's own Commons domain). Everything else — Works, Help &
# Support, KC Organizations, About, Team Blog — stays fixed regardless
# of network. KC Organizations lives ON the default domain, so this
# must be an explicit key allowlist rather than a hostname match.
NETWORK_AWARE_NAV_KEYS = frozenset(
    {"NAV_NEWS_FEED_URL", "NAV_GROUPS_URL", "NAV_SITES_URL"}
)


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

    default_domain = getattr(settings, "NAV_DEFAULT_DOMAIN", "hcommons.org")

    # a network host or path prefix (NetworkSubdomainMiddleware) pins
    # the community links to that network's Commons domain. With no
    # network context the links always stay on the environment's own
    # domains — there is deliberately no referer- or session-based
    # stickiness, so leaving a network never leaves the nav stuck on
    # that network's domain.
    network_slug = getattr(request, "network_slug", None)
    if network_slug:
        target_domain = network_domain(network_slug, default_domain)
        return {
            key: (
                _rewrite_domain(url, default_domain, target_domain)
                if key in NETWORK_AWARE_NAV_KEYS
                else url
            )
            for key, url in urls.items()
        }

    return urls
