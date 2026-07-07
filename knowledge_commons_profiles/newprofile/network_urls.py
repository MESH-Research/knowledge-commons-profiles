"""
Network-aware, environment-aware URL construction for Commons groups.

A Knowledge Commons group is tagged at creation with its home network's
``society_id`` (e.g. ``mla``, ``arlisna``) via a BuddyPress group type. The
base Commons groups carry ``hc`` (or no type at all). These helpers turn a
group's society id into the correct resolving URL:

* a network group resolves to ``{society}.{base}`` (or a configured override
  such as ``commons.msu.edu`` for ``msu``);
* a base-Commons group resolves to the environment's own domain.

The base domain is ``settings.NAV_DEFAULT_DOMAIN`` (``hcommons.org`` on prod,
``hcommons-dev.org`` on dev, ``hcommons-test.org`` on test), so every URL is
environment-aware. ``network_domain`` is the single source of truth shared
with the navbar context processor.
"""

from django.conf import settings

from knowledge_commons_profiles.newprofile.models import WpTerm
from knowledge_commons_profiles.newprofile.models import WpTermRelationships

# society ids that mean "the base Commons", not a network subdomain
BASE_SOCIETY_IDS = frozenset({"hc"})


def network_domain(society_id, default_domain):
    """
    Resolve the Commons domain for a group's society.

    A falsy ``society_id`` or one in :data:`BASE_SOCIETY_IDS` returns
    ``default_domain`` unchanged. Otherwise the domain is the configured
    ``NETWORK_DOMAIN_OVERRIDES`` entry for this deployment's
    ``NETWORK_DOMAIN_ENVIRONMENT`` (e.g. ``msu`` -> ``commons.msu.edu``),
    falling back to ``{society_id}.{default_domain}``.
    """
    if not society_id or society_id.lower() in BASE_SOCIETY_IDS:
        return default_domain

    slug = society_id.lower()
    overrides = getattr(settings, "NETWORK_DOMAIN_OVERRIDES", {})
    environment = getattr(settings, "NETWORK_DOMAIN_ENVIRONMENT", "main")
    override = overrides.get(slug, {}).get(environment)
    return override or f"{slug}.{default_domain}"


def group_url(society_id, slug, default_domain=None):
    """
    Build the resolving URL for a group.

    Returns ``https://{network_domain(society_id, base)}/groups/{slug}/``,
    where ``base`` defaults to ``settings.NAV_DEFAULT_DOMAIN``.
    """
    if default_domain is None:
        default_domain = settings.NAV_DEFAULT_DOMAIN
    domain = network_domain(society_id, default_domain)
    return f"https://{domain}/groups/{slug}/"


def society_ids_for_groups(group_ids):
    """
    Map each group id to its society id (BuddyPress group type slug).

    Reads the ``bp_group_type`` taxonomy on the WordPress root blog. Groups
    with no group type are absent from the mapping. The query is filtered to
    the ``bp_group_type`` taxonomy because ``wp_term_relationships.object_id``
    is shared across object types (users carry academic-interest terms there
    too).
    """
    group_ids = list(group_ids)
    if not group_ids:
        return {}

    type_rows = list(
        WpTermRelationships.objects.filter(
            object_id__in=group_ids,
            term_taxonomy__taxonomy="bp_group_type",
        ).values_list("object_id", "term_taxonomy__term_id")
    )

    term_ids = {term_id for _, term_id in type_rows}
    slug_by_term = (
        dict(
            WpTerm.objects.filter(term_id__in=term_ids).values_list(
                "term_id", "slug"
            )
        )
        if term_ids
        else {}
    )

    societies = {}
    for object_id, term_id in type_rows:
        slug = slug_by_term.get(term_id)
        if slug is not None:
            societies[object_id] = slug
    return societies
