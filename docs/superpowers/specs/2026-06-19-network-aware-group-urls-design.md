# Network-aware group URLs (issue #622)

## Problem

Group links in the right-hand "Groups" panel of a Profile are wrong in two
ways:

1. **Wrong base domain.** On `hcommons-dev.org` the links point at
   `https://hcommons-staging.org/groups/<slug>/`. The base is
   `settings.WORDPRESS_DOMAIN`, injected by the `mysql_data` HTMX view
   (`htmx.py:417`) and rendered in `mysql_data.html:13`:

   ```html
   <a class="interest-link"
      href="https://{{ wordpress_domain }}/groups/{{ group.slug }}/">
   ```

   On dev `WORDPRESS_DOMAIN` defaults to `hcommons-staging.org`
   (`config/settings/dev.py:221`). It is not from the database.

2. **No network awareness.** Every group resolves to one flat domain. An
   MLA group such as `20th-and-21st-century-american` should resolve to
   `https://mla.hcommons-dev.org/groups/20th-and-21st-century-american/`,
   not the base Commons.

## How a group maps to a network

The linkage lives in the `humanities-commons` WordPress plugin and is built
on **BuddyPress group types**, not group meta:

- Each network has a `society_id` (network option in `wp_sitemeta`):
  `mla.hcommons.org → "mla"`, `arlisna.hcommons.org → "arlisna"`, the base
  Commons → `"hc"`.
- On creation a group is permanently tagged with its network's `society_id`
  as a BuddyPress group type via `bp_groups_set_group_type($id, society_id)`,
  stored in the `bp_group_type` taxonomy on the **root blog**.
- Permalinks for a group on a foreign network are rewritten to the group's
  home-network domain.

So the source of truth for a group's network is its `bp_group_type` term
slug. Confirmed: the term slug is the **bare** `society_id` (`mla`), not a
prefixed form.

### Django-side data access

- `wp_term_taxonomy` → `WpTermTaxonomy` (exists)
- `wp_term_relationships` → `WpTermRelationships` (exists; `object_id` is the
  group id for `bp_group_type` rows)
- `wp_terms` → **no model yet**; needs `WpTerm` (`term_id`, `name`, `slug`)

`ReadWriteRouter` routes any model whose name starts with `wp` to the
`wordpress_dev` database, so `WpTerm` needs no extra wiring. The taxonomy
tables are unprefixed (root-blog taxonomy), which is where group types live.

`object_id` in `wp_term_relationships` is shared across object types
(users carry academic-interest terms there too), so queries **must** filter
`term_taxonomy__taxonomy="bp_group_type"` to isolate group types.

## Base domain (environment awareness)

The base Commons domain is read from `settings.NAV_DEFAULT_DOMAIN`
(`hcommons.org` / `hcommons-dev.org` / `hcommons-test.org`). Per decision,
this value is **sourced from the deployment environment** — the running
dev/test boxes set it. This change does **not** add settings defaults and
does **not** touch the navbar links. (The repo's local `.envs/.dev/.django`
does not set it; that is a local-only gap and out of scope.)

## Design

### New module: `newprofile/network_urls.py`

Single source of truth for network → domain resolution, shared with the
navbar context processor.

```python
def network_domain(society_id, default_domain):
    """Domain for a group's society.

    Falsy society_id or "hc" -> default_domain (base Commons).
    Otherwise NETWORK_DOMAIN_OVERRIDES[slug][env] (e.g. msu ->
    commons.msu.edu / msucommons-dev.org), else f"{slug}.{default_domain}".
    """

def group_url(society_id, slug, default_domain=None):
    """https://{network_domain(...)}/groups/{slug}/

    default_domain defaults to settings.NAV_DEFAULT_DOMAIN.
    """
```

`context_processors._network_domain` is re-pointed at
`network_urls.network_domain` so there is one implementation. The existing
`_rewrite_domain` import path in `context_processors` is preserved so the
current nav tests keep passing.

### New model: `WpTerm`

```python
class WpTerm(models.Model):
    term_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=200)
    class Meta:
        db_table = "wp_terms"
        managed = False
```

### `api.get_groups`

After assembling the group list, one bulk query resolves each group's
society, then a bulk `WpTerm` lookup resolves slugs:

```python
group_ids = [g["id"] for g in groups]
type_rows = (
    WpTermRelationships.objects.filter(
        object_id__in=group_ids,
        term_taxonomy__taxonomy="bp_group_type",
    ).values_list("object_id", "term_taxonomy__term_id")
)
slug_by_term = dict(
    WpTerm.objects.filter(term_id__in={t for _, t in type_rows})
    .values_list("term_id", "slug")
)
society_by_group = {oid: slug_by_term.get(tid) for oid, tid in type_rows}
```

Each group dict gains `url = group_url(society_by_group.get(g["id"]),
g["slug"])`. Existing keys are unchanged, so the REST
`GroupMembershipSerializer` (which builds its own API URL via `reverse`) is
unaffected.

### Sidebar template

`mysql_data.html:13` becomes `href="{{ group.url }}"`.

### REST `GroupDetailSerializer.get_url`

Replace `f"{settings.NAV_GROUPS_URL}{obj.slug}/"` with a network-aware build:
resolve the single group's `bp_group_type` slug and return
`group_url(society_id, obj.slug)`. The existing serializer tests override
`NAV_GROUPS_URL`; they will be updated to override `NAV_DEFAULT_DOMAIN`
instead, since the base now comes from there.

## Edge cases

| Group state | Resolves to |
|---|---|
| `bp_group_type` slug = `mla` | `https://mla.<base>/groups/<slug>/` |
| `bp_group_type` slug = `msu` | override domain (e.g. `commons.msu.edu`) |
| slug = `hc` | base Commons |
| no `bp_group_type` row | base Commons |
| multiple group-type rows | first slug that is not `hc`/empty, else base |

## Testing (red/green; all WordPress deps mocked)

Tests never connect to `wordpress_dev`, so WP model access is mocked.

- `network_urls` unit tests: base domain, `hc`, a network slug, an override
  (msu), empty/None.
- `api.get_groups`: a group typed `mla` yields `https://mla.<base>/groups/
  <slug>/`; an untyped group yields the base; taxonomy filter is exercised
  by mocking the relationship/term lookups.
- `GroupDetailSerializer`: network-aware URL for a typed group; base for an
  untyped group.
- One nav regression test confirming the `_network_domain` refactor did not
  change navbar behavior.

## Out of scope

- Navbar link behavior (unchanged).
- Settings defaults for `NAV_DEFAULT_DOMAIN` (deployment-sourced).
- The local `.envs/.dev/.django` gap.
