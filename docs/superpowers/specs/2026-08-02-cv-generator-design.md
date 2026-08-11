# CV Generator — Design

Date: 2026-08-02
Status: approved

## Purpose

Let profile users generate an academic CV as a PDF from the metadata that
institutional repositories hold about them — KC Works by default, plus any
number of additional InvenioRDM or eprints repositories — combined with
rich-text sections they write themselves. The generated PDF lands in the
profile's existing CV slot (`Profile.cv_file`) and can be regenerated from a
small link on the profile edit page. The engine is a port of the existing
standalone `eprintsToCV` tool (at `~/Documents/Programming/eprintsToCV`),
whose pipeline (multi-repository fetch, DOI/title dedupe, citeproc-js
citation formatting, Paged.js + headless-Chromium PDF printing) is kept
intact; its file-based configuration and caching edges are replaced with
Django models and a web UI. The UI must be usable by non-technical users:
type into rich-text blocks, drag sections into order, press Refresh, press
Generate.

## Decisions (settled during brainstorming)

- **PDF engine:** Paged.js + Playwright-driven headless Chromium, ported
  as-is from eprintsToCV for exact visual and accessibility fidelity
  (tagged PDF, document outline, page folios).
- **Long-running work:** background daemon threads + status fields +
  HTMX polling. No new queue infrastructure.
- **Citations:** citeproc-js on mini-racer (embedded V8), vendored CSL
  styles/locales, as in eprintsToCV. The project's existing Python
  citeproc app remains untouched for works.py.
- **Outputs:** PDF only. HTML is used internally for preview and as the
  print source, but the only published artifact is the PDF.
- **CV count:** multiple named CVs per user; exactly one may be active;
  the active CV's PDF feeds `Profile.cv_file`.
- **Default layout:** Header → "Appointments" (empty rich text) →
  "Education" (empty rich text) → Books → Edited Volumes →
  Peer-Reviewed Articles → Footer.
- **Footer block:** rich text plus an optional auto-inserted
  "Last updated <date>" line.
- **Advanced tab exposes:** citation style + locale; per-repository
  search strategies; filtering & display options (exclude venues,
  italicize titles, "Review of" prefix, gold-OA direct links,
  title-vs-entry linking); identity overrides (name/emails/ORCID used
  for matching and the header, without altering the profile).
- **Scope of settings:** repositories, identity overrides, and the
  fetched-works cache are per-user (one merged corpus, one Refresh);
  layout blocks, citation style, and display options are per-CV.
- **File naming:** `Profile.cv_file` (uploads and generated files alike)
  moves to `cvs/{uuid4}.{ext}`. The existing pre_save signal deletes the
  replaced file.

## Architecture

New Django app `knowledge_commons_profiles.cv_generator`:

```
cv_generator/
  pipeline/          # ported from eprintsToCV cv/ package
    invenio.py       # InvenioRDM fetching (KC Works, Zenodo, …)
    repository.py    # eprints fetching
    sources.py       # search-strategy resolution
    dedupe.py        # DOI + title-fallback merging
    provenance.py    # human-readable fetch/merge audit log
    citeproc.py      # citeproc-js via mini-racer
    renderer.py      # block/section HTML rendering
    printpdf.py      # Paged.js printing via Playwright Chromium
  models.py          # CVRepository, CVWorksStore, CVIdentity,
                     # CurriculumVitae, CVBlock
  views/             # list, builder, block CRUD/reorder, refresh,
                     # generate, status-poll, repository CRUD, advanced
  services.py        # thread orchestration, works-store update,
                     # generation + file placement
  static/cv_generator/   # citeproc-js, CSL styles + locales, Paged.js,
                         # CV print CSS (vendored)
  templates/cv_generator/  # list page, builder (3 tabs), PDF template,
                           # HTMX fragments
  tests/
```

The pipeline keeps eprintsToCV's merge semantics with one change: the
user-controlled `position` ordering of `CVRepository` rows fully governs
precedence (eprintsToCV hard-coded eprints-before-InvenioRDM; here the
Repositories tab's order is authoritative). The first repository's record
is preferred and its gaps are filled from later copies; duplicates are
dropped by DOI, falling back to title matching.
Storage moves from `data/*.json` files to the `CVWorksStore` row; the
per-user Python config module is replaced by model fields.

## Data model

- **`CVRepository`** — profile FK; `kind` (`invenio` | `eprints`);
  `endpoint` (API URL for Invenio, hostname for eprints); `label`;
  `position` (merge precedence); `search_config` JSON
  (`{"strategies": [...], "mode": "union" | "first"}`). A KC Works row is
  auto-created on the user's first visit, configured to search by KC
  username identifier (as `newprofile/works.py` does today) plus ORCID
  plus name, in union mode — so it works for users without an ORCID.
- **`CVWorksStore`** — one per profile: `records` JSON (merged, deduped,
  classified works), `provenance` text, `fetched_at`, `status`
  (`idle` | `fetching` | `error`), `error_detail`.
- **`CVIdentity`** — one per profile: optional overrides for display
  name, emails, ORCID. Blank fields fall back to `Profile`.
- **`CurriculumVitae`** — profile FK; `name`; `is_active` (partial
  unique constraint: at most one active per profile); `citation_style`
  (default seeded from `Profile.reference_style`); `citation_locale`;
  `citation_link` (`title` | `entry`); `gold_oa_direct_link` bool;
  `review_of` prefix; `titles_to_italicize` (text, one per line);
  `exclude_venues` JSON (per works type); `generated_file` (FileField,
  UUID path); `generated_at`; `generation_status`
  (`idle` | `generating` | `error`); `error_detail`.
- **`CVBlock`** — CV FK; `position`; `kind`
  (`header` | `richtext` | `publications` | `footer`); `heading`;
  `content` (sanitized HTML; richtext/footer only); `works_type`
  (publications only: `unedited_books`, `edited_books`,
  `peer_reviewed_articles`, `other_articles`, `reviews`,
  `book_chapters`, `conference_items`, `all_books`,
  `all_peer_reviewed_articles`); `show_last_updated` (footer only).

Works-type classification (peer-reviewed / editorial / book-review
conditions, eprints DB types, CSL type mapping) ships as module-level
defaults copied from eprintsToCV's config; it is not user-exposed.

## Flows

### Refresh

POST to the refresh endpoint → `CVWorksStore.status = fetching` → daemon
thread → for each `CVRepository` in position order run its strategies,
merge, dedupe, classify → write `records` + `provenance`, set `fetched_at`,
`status = idle`. The builder polls a status endpoint via HTMX (~2s) and
swaps in per-type counts and the fetched-at stamp. A `fetching` status
older than 10 minutes is treated as failed (container-restart protection).
Per-repository failures are recorded in provenance and shown per-source
("KC Works: 63 items · Birkbeck eprints: failed"); the refresh continues
with remaining repositories. A totally failed refresh leaves the previous
store untouched.

### Generate

POST to the generate endpoint → `generation_status = generating` → daemon
thread → render blocks to HTML → print to PDF → save bytes to
`CurriculumVitae.generated_file` under `cv_generator/{uuid4}.pdf`; if
`is_active`, also set `Profile.cv_file` (UUID name, old file auto-deleted
by the existing signal). HTMX polling as above; on success the UI links
the fresh PDF. Rendering details:

- **Header block:** name, "Curriculum Vitae" line, title/affiliation
  lines, emails as mailto links, ORCID link — from `CVIdentity` falling
  back to `Profile` — matching the PersonInfo layout of the reference
  PDF (`eprintsToCV/output/martin_paul_eve.pdf`).
- **Rich-text/footer blocks:** sanitized HTML under the block's heading;
  footer optionally appends "Last updated <date>".
- **Publications blocks:** records of the block's works type formatted
  through citeproc-js with the CV's style/locale, year-in-left-margin
  item templates, heading with count ("BOOKS (16)"), honouring the CV's
  display options (link mode, gold-OA links, italicize titles, exclude
  venues, "Review of" grouping).
- **Printing:** ported Paged.js PDF template + CSS; Playwright Chromium
  waits for `window.__pagedDone`; tagged PDF with outline and language;
  hard timeout ~120s; a semaphore caps concurrent Chromium instances
  (default 2). Generation errors leave the previous PDF in place.

### Edit-page integration

Next to the CV file field on the profile edit page: an "Update from
repositories" link (refresh + regenerate the active CV as one background
job, surfacing the new file in the existing upload UI when done) and an
"Open CV Builder" link. Manual upload remains; upload and generation both
write `Profile.cv_file`, last writer wins.

## UI

URLs under `/cv/` (login required; users act on their own data; staff may
act on others', mirroring `upload_cv`).

- **My CVs list:** name, active badge, last generated, actions (edit,
  rename, duplicate, delete, make active, download PDF), "Create a CV"
  (pre-filled default layout). First visit auto-creates a first CV and
  enters the builder.
- **Builder, tab 1 "Build" (default):** left palette of insertable
  blocks with plain-English names; right canvas of ordered block cards;
  SortableJS drag-to-reorder, palette drag-in plus click-to-add
  (keyboard-accessible) fallback; per-card drag handle, editable
  heading, delete. Rich-text/footer cards embed TinyMCE (`SanitizedTinyMCE`
  pathway). Publications cards show live counts and a short citation
  preview (read-only). Header card shows resolved identity with a link
  to Advanced. Top bar: Refresh publications (with polling status),
  Preview (HTML in modal iframe, no Chromium), Generate PDF, and
  debounced autosave of order/content/headings.
- **Tab 2 "Repositories":** CRUD + reorder of `CVRepository`. Add form:
  type, URL, friendly name; search strategies under a collapsed "how we
  find your work" panel with plain-language labels. Reordering sets
  merge precedence ("if a work appears in two places, the higher
  repository wins"). Deleting prompts a refresh.
- **Tab 3 "Advanced":** per-CV citation style/locale, link mode, gold-OA
  linking, "Review of" prefix, italicize-titles list, exclude venues;
  per-user identity overrides pre-filled from the profile. Everything
  defaulted; nothing required; short helper text throughout.

## Security

- Rich-text content sanitized server-side on save and again at render
  time (it is executed inside a server-side Chromium).
- Repository endpoints validated: http/https only, no internal-network
  addresses (same SSRF posture as the broker's allowed-domain checks;
  reuse existing URL-validation helpers where present).
- citeproc-js runs in mini-racer with no I/O surface.
- All querysets scoped to the requesting user (staff override).

## Error handling summary

- Per-repo fetch failure: logged to provenance, shown per-source, other
  repositories still merge.
- Full refresh failure: previous works store preserved.
- Generation failure: `generation_status = error`, friendly message,
  previous PDF untouched; no partial files.
- Timeouts on all external calls; stale in-flight statuses self-expire.

## Testing

Red/green TDD throughout. Port the eprintsToCV test suite for the
pipeline modules, adapted to DB-backed storage — including the
golden-citations fixtures, which pin citation-output fidelity. New tests:
model constraints (single active CV, block ordering), works-type
classification, header rendering (profile vs overrides), sanitization,
refresh/generate state machines (threads and HTTP mocked), view
permissions, UUID file naming and active-CV-to-profile placement.
Chromium printing is mocked in unit tests, with one integration test
skipped when Playwright is unavailable.

## Deployment

- New dependencies via uv: `playwright`, `mini-racer`.
- Dockerfile: `playwright install --with-deps chromium` layer.
- Vendored static assets served through collectstatic.
- No data backfill; users get rows on first visit. Feature reachable
  only through the new links, so rollout is low-risk.
