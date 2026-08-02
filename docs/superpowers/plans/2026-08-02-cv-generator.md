# CV Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A web CV builder in knowledge_commons_profiles: users assemble drag-and-drop CV blocks (header, rich text, per-type publication lists, footer) fed from configurable repositories (KC Works by default, plus any InvenioRDM/eprints), and generate an accessible PDF into their profile's CV slot.

**Architecture:** New Django app `knowledge_commons_profiles.cv_generator` containing a port of the eprintsToCV pipeline (source at `/home/martin/Documents/Programming/eprintsToCV` — referred to below as `$EPRINTSTOCV`). The pipeline's file-based edges (Python-module config, `data/*.json` cache, `output/` files) are replaced by models: per-user `CVRepository`/`CVWorksStore`/`CVIdentity`, per-CV `CurriculumVitae`/`CVBlock`. Long work (fetch, PDF render) runs in daemon threads with status fields polled via HTMX. PDF printing is Paged.js in Playwright-driven headless Chromium; citations are citeproc-js on mini-racer.

**Tech Stack:** Django 5, PostgreSQL (JSONField/ArrayField), HTMX 1.9 (already in base.html), jQuery UI sortable (already in static/js, used by profile-sort.js), TinyMCE (via existing `SanitizedTinyMCE`/`sanitize_html`), `requests` (already a dep), `py-mini-racer` (new), `playwright` (new).

**Spec:** `docs/superpowers/specs/2026-08-02-cv-generator-design.md`. Read it before starting any task.

## Global Constraints

- Python is run with uv: `uv run --group local ./manage.py <cmd>`.
- Test command (run from repo root):
  `PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.local DJANGO_READ_DOT_ENV_FILE=True uv run --group local ./manage.py test knowledge_commons_profiles.cv_generator`
  (append other app paths when a task touches them; run the FULL suite — no app path — before every commit, per user policy).
- TDD is red/green: every test is written first against a stub that raises `NotImplementedError` (or against a not-yet-changed behaviour) and MUST be run and seen to fail before implementing. Tests assert behaviour (inputs → outputs), never call counts or logging.
- Tests are unittest-style (`django.test.SimpleTestCase` for pure code, `TestCase` for DB) — the project runs them via `manage.py test`, not pytest. Ported pytest tests must be converted.
- Run `pre-commit run --files <changed files>` before every commit; fix failures and re-stage.
- Commits: conventional style, e.g. `feat(cv): …`. The user has not yet given a GitHub issue number; if one is provided during execution, add it to each commit footer. Never credit an AI.
- Do all work on branch `feature/cv-generator` off `main` (rename to `feature/cv-generator-<issue#>` if an issue number is supplied).
- The mocked-HTTP rule: no test may hit the network or a real browser. `requests.get` and Playwright are always mocked in unit tests.
- All user-supplied HTML goes through `knowledge_commons_profiles.newprofile.utils.sanitize_html` on save AND at render time.
- Copy source files from `$EPRINTSTOCV = /home/martin/Documents/Programming/eprintsToCV`. When a step says "copy", use `cp` then apply only the edits shown; do not rewrite ported code.
- New profile fields / behaviour changes must not break the existing 1426-test suite; where a test encodes replaced behaviour (e.g. `cvs/{pk}` file naming), the task says explicitly to update it.

---

### Task 1: App skeleton, settings and URL registration

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/__init__.py` (empty)
- Create: `knowledge_commons_profiles/cv_generator/apps.py`
- Create: `knowledge_commons_profiles/cv_generator/migrations/__init__.py` (empty)
- Create: `knowledge_commons_profiles/cv_generator/urls.py`
- Create: `knowledge_commons_profiles/cv_generator/views/__init__.py` (empty)
- Create: `knowledge_commons_profiles/cv_generator/tests/__init__.py` (empty)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_apps.py`
- Modify: `config/settings/base.py` (LOCAL_APPS, line ~105)
- Modify: `config/urls.py` (urlpatterns, after the newprofile include at line 20)

**Interfaces:**
- Consumes: nothing.
- Produces: installed app label `cv_generator`; URL namespace `cv_generator` mounted at `/cv/` (empty urlpatterns for now — later tasks append to `knowledge_commons_profiles/cv_generator/urls.py`).

- [ ] **Step 1: Write the failing test**

`knowledge_commons_profiles/cv_generator/tests/test_apps.py`:

```python
"""The cv_generator app is installed and its URLs are mounted."""

from django.apps import apps
from django.test import SimpleTestCase
from django.urls import get_resolver


class AppRegistrationTests(SimpleTestCase):
    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("knowledge_commons_profiles.cv_generator"))

    def test_url_namespace_is_mounted(self):
        resolver = get_resolver()
        self.assertIn("cv_generator", resolver.namespace_dict)
```

Also create the empty `__init__.py` files listed above so the test module imports.

- [ ] **Step 2: Run tests to verify they fail**

Run the test command (Global Constraints) with app path `knowledge_commons_profiles.cv_generator`.
Expected: both tests FAIL (`False is not true` / `'cv_generator' not found in namespace_dict`).

- [ ] **Step 3: Implement**

`knowledge_commons_profiles/cv_generator/apps.py`:

```python
from django.apps import AppConfig


class CVGeneratorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge_commons_profiles.cv_generator"
    label = "cv_generator"
```

`knowledge_commons_profiles/cv_generator/urls.py`:

```python
"""URLs for the CV generator."""

app_name = "cv_generator"

urlpatterns = []
```

In `config/settings/base.py`, append to `LOCAL_APPS` (after the pages entry):

```python
    "knowledge_commons_profiles.cv_generator.apps.CVGeneratorConfig",
```

In `config/urls.py`, after the `newprofile.urls` include:

```python
    path("cv/", include("knowledge_commons_profiles.cv_generator.urls")),
```

- [ ] **Step 4: Run tests to verify they pass**

Same command. Expected: 2 tests PASS.

- [ ] **Step 5: Full suite, pre-commit, commit**

Run the FULL test suite (no app path). Expected: all pass.

```bash
git checkout -b feature/cv-generator
git add knowledge_commons_profiles/cv_generator config/settings/base.py config/urls.py
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add cv_generator app skeleton"
```

---

### Task 2: Models and migration

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/models.py`
- Create: `knowledge_commons_profiles/cv_generator/admin.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_models.py`
- Create (generated): `knowledge_commons_profiles/cv_generator/migrations/0001_initial.py`

**Interfaces:**
- Consumes: `knowledge_commons_profiles.newprofile.models.Profile`, `CITATION_STYLE_CHOICES` (from `newprofile.models`).
- Produces (used by every later task):
  - `WORKS_TYPES: list[tuple[str, str]]` — machine name → plain-English label, in this exact order: `all_books`/"All books", `unedited_books`/"Books", `edited_books`/"Edited volumes", `all_peer_reviewed_articles`/"All peer-reviewed articles", `peer_reviewed_articles`/"Peer-reviewed articles", `other_articles`/"Other articles", `reviews`/"Reviews", `book_chapters`/"Book chapters", `conference_items`/"Conference papers".
  - `CVRepository(profile, kind, endpoint, label, position, search_config)` with `KIND_INVENIO = "invenio"`, `KIND_EPRINTS = "eprints"`; default ordering `["position", "id"]`.
  - `CVWorksStore(profile 1:1, records, provenance, fetched_at, status, status_changed_at, error_detail)` with `STATUS_IDLE/FETCHING/ERROR = "idle"/"fetching"/"error"` and method `fetch_is_stalled() -> bool` (fetching for > 10 minutes).
  - `CVIdentity(profile 1:1, name, emails, orcid)` — all blank-able overrides.
  - `CurriculumVitae(profile FK related_name="cvs", name, is_active, citation_style, citation_locale, citation_link, gold_oa_direct_link, review_of, titles_to_italicize, exclude_venues, generated_file, generated_at, generation_status, generation_started_at, error_detail)` with `STATUS_IDLE/GENERATING/ERROR`, method `generation_is_stalled() -> bool`, and DB constraint: at most one `is_active=True` per profile.
  - `CVBlock(cv FK related_name="blocks", position, kind, heading, content, works_type, show_last_updated)` with `KIND_HEADER/RICHTEXT/PUBLICATIONS/FOOTER = "header"/"richtext"/"publications"/"footer"`; ordering `["position", "id"]`.
  - `generated_pdf_path(instance, filename) -> "cv_generator/<uuid4hex>.pdf"`.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_models.py`:

```python
"""Model behaviour for the CV generator."""

import re
from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVRepository,
    CVWorksStore,
    CurriculumVitae,
    generated_pdf_path,
)
from knowledge_commons_profiles.newprofile.models import Profile


def make_profile(username="kcuser"):
    return Profile.objects.create(name="Test User", username=username)


class GeneratedPdfPathTests(TestCase):
    def test_path_is_uuid_named_pdf_under_cv_generator(self):
        path = generated_pdf_path(None, "whatever.pdf")
        self.assertRegex(path, r"^cv_generator/[0-9a-f]{32}\.pdf$")

    def test_two_calls_never_collide(self):
        self.assertNotEqual(
            generated_pdf_path(None, "a.pdf"), generated_pdf_path(None, "a.pdf")
        )


class CurriculumVitaeTests(TestCase):
    def test_only_one_active_cv_per_profile(self):
        profile = make_profile()
        CurriculumVitae.objects.create(profile=profile, name="A", is_active=True)
        with self.assertRaises(IntegrityError):
            CurriculumVitae.objects.create(
                profile=profile, name="B", is_active=True
            )

    def test_two_inactive_cvs_are_fine(self):
        profile = make_profile()
        CurriculumVitae.objects.create(profile=profile, name="A")
        CurriculumVitae.objects.create(profile=profile, name="B")
        self.assertEqual(profile.cvs.count(), 2)

    def test_active_cvs_on_different_profiles_are_fine(self):
        CurriculumVitae.objects.create(
            profile=make_profile("u1"), name="A", is_active=True
        )
        CurriculumVitae.objects.create(
            profile=make_profile("u2"), name="B", is_active=True
        )

    def test_generation_is_stalled_only_after_ten_minutes(self):
        cv = CurriculumVitae.objects.create(
            profile=make_profile(),
            generation_status=CurriculumVitae.STATUS_GENERATING,
            generation_started_at=timezone.now() - timedelta(minutes=11),
        )
        self.assertTrue(cv.generation_is_stalled())
        cv.generation_started_at = timezone.now() - timedelta(minutes=2)
        self.assertFalse(cv.generation_is_stalled())
        cv.generation_status = CurriculumVitae.STATUS_IDLE
        cv.generation_started_at = timezone.now() - timedelta(minutes=11)
        self.assertFalse(cv.generation_is_stalled())


class CVWorksStoreTests(TestCase):
    def test_fetch_is_stalled_only_when_fetching_too_long(self):
        store = CVWorksStore.objects.create(
            profile=make_profile(),
            status=CVWorksStore.STATUS_FETCHING,
            status_changed_at=timezone.now() - timedelta(minutes=11),
        )
        self.assertTrue(store.fetch_is_stalled())
        store.status_changed_at = timezone.now()
        self.assertFalse(store.fetch_is_stalled())
        store.status = CVWorksStore.STATUS_IDLE
        store.status_changed_at = timezone.now() - timedelta(minutes=60)
        self.assertFalse(store.fetch_is_stalled())


class OrderingTests(TestCase):
    def test_repositories_come_back_in_position_order(self):
        profile = make_profile()
        second = CVRepository.objects.create(
            profile=profile, kind="eprints", endpoint="eprints.example.org",
            position=2,
        )
        first = CVRepository.objects.create(
            profile=profile, kind="invenio",
            endpoint="https://works.hcommons.org/api/records", position=1,
        )
        self.assertEqual(list(profile.cv_repositories.all()), [first, second])

    def test_blocks_come_back_in_position_order(self):
        cv = CurriculumVitae.objects.create(profile=make_profile())
        b2 = CVBlock.objects.create(cv=cv, kind="richtext", position=2)
        b1 = CVBlock.objects.create(cv=cv, kind="header", position=1)
        self.assertEqual(list(cv.blocks.all()), [b1, b2])
```

- [ ] **Step 2: Create stub models file and run tests to verify they fail**

Create `knowledge_commons_profiles/cv_generator/models.py` containing ONLY:

```python
"""Models for the CV generator."""


def generated_pdf_path(instance, filename):
    raise NotImplementedError
```

Run the cv_generator tests. Expected: FAIL/ERROR on import of the model classes (`ImportError`) — acceptable here because the classes cannot be stubbed as models without a migration; the behavioural failures are exercised in step 4's first run.

- [ ] **Step 3: Implement models**

Replace `knowledge_commons_profiles/cv_generator/models.py` with:

```python
"""Models for the CV generator.

Per-user state (repositories, the fetched works corpus, identity
overrides) is shared by all of a user's CVs; per-CV state is the block
layout plus citation/display options. See the design spec.
"""

import uuid
from datetime import timedelta

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from knowledge_commons_profiles.newprofile.models import CITATION_STYLE_CHOICES

# how long an in-flight fetch/generation may run before it is presumed
# dead (e.g. the container restarted mid-job) and may be restarted
STALLED_AFTER = timedelta(minutes=10)

WORKS_TYPES = [
    ("all_books", "All books"),
    ("unedited_books", "Books"),
    ("edited_books", "Edited volumes"),
    ("all_peer_reviewed_articles", "All peer-reviewed articles"),
    ("peer_reviewed_articles", "Peer-reviewed articles"),
    ("other_articles", "Other articles"),
    ("reviews", "Reviews"),
    ("book_chapters", "Book chapters"),
    ("conference_items", "Conference papers"),
]


def generated_pdf_path(instance, filename):
    """A collision-proof storage path for a generated CV PDF."""
    return f"cv_generator/{uuid.uuid4().hex}.pdf"


class CVRepository(models.Model):
    """One repository a user's works are fetched from."""

    KIND_INVENIO = "invenio"
    KIND_EPRINTS = "eprints"
    KIND_CHOICES = [
        (KIND_INVENIO, "InvenioRDM (KC Works, Zenodo, …)"),
        (KIND_EPRINTS, "eprints"),
    ]

    profile = models.ForeignKey(
        "newprofile.Profile",
        on_delete=models.CASCADE,
        related_name="cv_repositories",
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    # API URL for InvenioRDM entries, hostname for eprints entries
    endpoint = models.CharField(max_length=500)
    label = models.CharField(max_length=255, blank=True)
    # merge precedence: lower position wins conflicts
    position = models.PositiveIntegerField(default=0)
    # {"strategies": [...], "mode": "union"|"first"}; empty = defaults
    search_config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "CV repositories"

    def __str__(self):
        return f"{self.label or self.endpoint} ({self.profile.username})"


class CVWorksStore(models.Model):
    """The merged, deduplicated works corpus for one profile."""

    STATUS_IDLE = "idle"
    STATUS_FETCHING = "fetching"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_IDLE, "Idle"),
        (STATUS_FETCHING, "Fetching"),
        (STATUS_ERROR, "Error"),
    ]

    profile = models.OneToOneField(
        "newprofile.Profile",
        on_delete=models.CASCADE,
        related_name="cv_works_store",
    )
    records = models.JSONField(default=list, blank=True)
    provenance = models.TextField(blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_IDLE
    )
    status_changed_at = models.DateTimeField(default=timezone.now)
    error_detail = models.TextField(blank=True)

    def fetch_is_stalled(self):
        """Whether an in-flight fetch has been running suspiciously long."""
        return (
            self.status == self.STATUS_FETCHING
            and self.status_changed_at < timezone.now() - STALLED_AFTER
        )

    def __str__(self):
        return f"Works store for {self.profile.username}"


class CVIdentity(models.Model):
    """Per-user identity overrides for CV building.

    Blank fields fall back to the profile's own name/emails/ORCID.
    """

    profile = models.OneToOneField(
        "newprofile.Profile",
        on_delete=models.CASCADE,
        related_name="cv_identity",
    )
    name = models.CharField(max_length=255, blank=True)
    emails = ArrayField(
        models.CharField(max_length=254), default=list, blank=True
    )
    orcid = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "CV identities"

    def __str__(self):
        return f"CV identity for {self.profile.username}"


class CurriculumVitae(models.Model):
    """One named CV layout; the active one feeds Profile.cv_file."""

    STATUS_IDLE = "idle"
    STATUS_GENERATING = "generating"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_IDLE, "Idle"),
        (STATUS_GENERATING, "Generating"),
        (STATUS_ERROR, "Error"),
    ]

    LINK_TITLE = "title"
    LINK_ENTRY = "entry"
    LINK_CHOICES = [
        (LINK_TITLE, "Link each item's title"),
        (LINK_ENTRY, "Link the whole citation"),
    ]

    profile = models.ForeignKey(
        "newprofile.Profile", on_delete=models.CASCADE, related_name="cvs"
    )
    name = models.CharField(max_length=255, default="My CV")
    is_active = models.BooleanField(default=False)

    citation_style = models.CharField(
        max_length=255, default="MHRA", choices=CITATION_STYLE_CHOICES
    )
    citation_locale = models.CharField(max_length=20, default="en-GB")
    citation_link = models.CharField(
        max_length=10, choices=LINK_CHOICES, default=LINK_TITLE
    )
    gold_oa_direct_link = models.BooleanField(default=True)
    review_of = models.CharField(max_length=100, default="Review of")
    # one title per line
    titles_to_italicize = models.TextField(blank=True)
    # {works_type: "venue1,venue2"}
    exclude_venues = models.JSONField(default=dict, blank=True)

    generated_file = models.FileField(
        upload_to=generated_pdf_path, blank=True, null=True
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    generation_status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_IDLE
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)
    error_detail = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile"],
                condition=models.Q(is_active=True),
                name="one_active_cv_per_profile",
            ),
        ]
        verbose_name_plural = "curricula vitae"

    def generation_is_stalled(self):
        """Whether an in-flight generation has run suspiciously long."""
        return (
            self.generation_status == self.STATUS_GENERATING
            and self.generation_started_at is not None
            and self.generation_started_at < timezone.now() - STALLED_AFTER
        )

    def __str__(self):
        return f"{self.name} ({self.profile.username})"


class CVBlock(models.Model):
    """One ordered block of a CV layout."""

    KIND_HEADER = "header"
    KIND_RICHTEXT = "richtext"
    KIND_PUBLICATIONS = "publications"
    KIND_FOOTER = "footer"
    KIND_CHOICES = [
        (KIND_HEADER, "Header"),
        (KIND_RICHTEXT, "Rich text"),
        (KIND_PUBLICATIONS, "Publications"),
        (KIND_FOOTER, "Footer"),
    ]

    cv = models.ForeignKey(
        CurriculumVitae, on_delete=models.CASCADE, related_name="blocks"
    )
    position = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=15, choices=KIND_CHOICES)
    heading = models.CharField(max_length=255, blank=True)
    # sanitized HTML; richtext and footer blocks only
    content = models.TextField(blank=True)
    # publications blocks only
    works_type = models.CharField(
        max_length=40, blank=True, choices=WORKS_TYPES
    )
    # footer blocks only
    show_last_updated = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.kind} block #{self.position} of {self.cv_id}"
```

`knowledge_commons_profiles/cv_generator/admin.py`:

```python
from django.contrib import admin

from knowledge_commons_profiles.cv_generator import models


@admin.register(models.CVRepository)
class CVRepositoryAdmin(admin.ModelAdmin):
    list_display = ("profile", "kind", "endpoint", "position")
    search_fields = ("profile__username", "endpoint")


class CVBlockInline(admin.TabularInline):
    model = models.CVBlock
    extra = 0


@admin.register(models.CurriculumVitae)
class CurriculumVitaeAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "is_active", "generation_status")
    search_fields = ("profile__username", "name")
    inlines = [CVBlockInline]


@admin.register(models.CVWorksStore)
class CVWorksStoreAdmin(admin.ModelAdmin):
    list_display = ("profile", "status", "fetched_at")
    search_fields = ("profile__username",)


@admin.register(models.CVIdentity)
class CVIdentityAdmin(admin.ModelAdmin):
    list_display = ("profile", "name", "orcid")
    search_fields = ("profile__username",)
```

Generate the migration:

```bash
DJANGO_SETTINGS_MODULE=config.settings.local DJANGO_READ_DOT_ENV_FILE=True uv run --group local ./manage.py makemigrations cv_generator
```

- [ ] **Step 4: Run tests to verify they pass**

Run the cv_generator tests. Expected: all model tests PASS.

- [ ] **Step 5: Full suite, pre-commit, commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add CV generator models"
```

---

### Task 3: UUID naming for Profile.cv_file

**Files:**
- Modify: `knowledge_commons_profiles/newprofile/models.py:42-63` (the `cv_file_path` function)
- Modify: `knowledge_commons_profiles/newprofile/tests/test_cv_upload.py` (assertions that encode `cvs/{pk}` naming)
- Test: `knowledge_commons_profiles/newprofile/tests/test_cv_upload.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `cv_file_path(instance, filename) -> "cvs/<uuid4hex><ext>"` — uploads AND generator-written files both get collision-proof, cache-busting names. The pre_save signal in `newprofile/signals.py` already deletes the replaced file; no change there.

- [ ] **Step 1: Write the failing test**

Read `knowledge_commons_profiles/newprofile/tests/test_cv_upload.py` first. Add this test class to it:

```python
class CvFilePathUuidTests(SimpleTestCase):
    """cv_file_path names files by UUID so replacements never collide
    and CDN caches never serve a stale CV (issue: CV generator)."""

    def test_path_is_uuid_named_with_original_extension(self):
        from knowledge_commons_profiles.newprofile.models import cv_file_path

        path = cv_file_path(None, "my resume.PDF")
        self.assertRegex(path, r"^cvs/[0-9a-f]{32}\.pdf$")

    def test_two_uploads_of_same_name_do_not_collide(self):
        from knowledge_commons_profiles.newprofile.models import cv_file_path

        self.assertNotEqual(
            cv_file_path(None, "cv.pdf"), cv_file_path(None, "cv.pdf")
        )
```

(`SimpleTestCase` is already imported in that file or add `from django.test import SimpleTestCase`.)

- [ ] **Step 2: Run tests to verify the new ones fail**

Run tests for `knowledge_commons_profiles.newprofile.tests.test_cv_upload`.
Expected: the two new tests FAIL (current implementation returns `cvs/None.pdf` / identical paths). Note which EXISTING tests in this file assert the old `cvs/{pk}` naming — they will be updated in step 3 because the naming scheme is intentionally changing.

- [ ] **Step 3: Implement**

Replace the body of `cv_file_path` in `knowledge_commons_profiles/newprofile/models.py` (keep the function name and signature; update the docstring):

```python
def cv_file_path(instance, filename):
    """
    Generate a collision-proof upload path for CV files.

    Files are stored as: cvs/{uuid4}.{extension}. A fresh UUID per write
    means a replaced CV never reuses its predecessor's URL, so CDN and
    browser caches cannot serve a stale file, and concurrent writers
    cannot clash.

    Args:
        instance: The Profile instance the file is being attached to
            (unused; kept for Django's upload_to contract)
        filename: The original filename of the uploaded file

    Returns:
        The path where the file should be stored,
        e.g. "cvs/3f2a…c9.pdf"
    """
    ext = Path(filename).suffix.lower()

    return f"cvs/{uuid.uuid4().hex}{ext}"
```

Add `import uuid` to the imports of `newprofile/models.py` if absent (`Path` is already imported there for the current implementation; if not, add `from pathlib import Path`).

Update any existing tests in `test_cv_upload.py`/`test_cv_delete.py` that assert `cvs/{pk}`-style names: change the assertion to match `r"^cvs/[0-9a-f]{32}\.pdf$"` (behavioural intent: file lands under `cvs/` with its extension preserved).

- [ ] **Step 4: Run tests to verify they pass**

Run `knowledge_commons_profiles.newprofile.tests.test_cv_upload` and `…test_cv_delete`. Expected: PASS.

- [ ] **Step 5: Full suite, pre-commit, commit**

```bash
git add knowledge_commons_profiles/newprofile
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): name CV files by UUID to avoid collisions and stale caches"
```

---

### Task 4: Pipeline port — dedupe and provenance

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/__init__.py` (empty)
- Create: `knowledge_commons_profiles/cv_generator/pipeline/dedupe.py` (copied)
- Create: `knowledge_commons_profiles/cv_generator/pipeline/provenance.py` (copied)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_dedupe.py` (ported)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_provenance.py` (ported)

**Interfaces:**
- Consumes: nothing (both modules are pure).
- Produces:
  - `dedupe.merge_records(primary: list[dict], secondary: list[dict], recorder=None) -> list[dict]`, `dedupe.normalise_doi(doi) -> str`, `dedupe.record_dois(record) -> set[str]`.
  - `provenance.ProvenanceRecorder(profile=None)` with `.search_ran(source, strategy, query, count, mode)`, `.search_skipped(source, strategy, reason)`, `.record_skipped(source, identifier, reason)`, `.base_records(source, records)`, `.for_source(source)`, and — NEW in this port — `.note(text)` (free-text event, used later for per-repository fetch failures) and `.render() -> str` (public rendering of the log text; the file-writing `write()` method is dropped).

- [ ] **Step 1: Port the tests (they must fail first)**

Copy the pytest tests and convert them to unittest style:

```bash
cp $EPRINTSTOCV/tests/test_dedupe.py knowledge_commons_profiles/cv_generator/tests/test_pipeline_dedupe.py
cp $EPRINTSTOCV/tests/test_provenance.py knowledge_commons_profiles/cv_generator/tests/test_pipeline_provenance.py
```

Conversion pattern (apply to every ported test file in this plan):

1. Change imports `from cv.X import Y` → `from knowledge_commons_profiles.cv_generator.pipeline.X import Y`.
2. Wrap the module's test functions as methods of one `class <Name>Tests(SimpleTestCase):` (add `from django.test import SimpleTestCase`); `def test_foo():` → `def test_foo(self):`.
3. Replace bare `assert a == b` with `self.assertEqual(a, b)`; `assert x` → `self.assertTrue(x)`; `assert x in y` → `self.assertIn(x, y)`; `pytest.raises(E)` → `self.assertRaises(E)`.
4. pytest fixtures become helper methods or `setUp`; `@pytest.mark.parametrize` becomes a `for` loop over `(input, expected)` tuples inside one test with `self.subTest(...)`.
5. Drop any test that exercises on-disk file writing (`write()` / tmp_path fixtures). For provenance, replace the file-writing test with:

```python
    def test_render_returns_the_log_text(self):
        recorder = ProvenanceRecorder(profile="kcuser")
        recorder.base_records("KC Works", [{"title": "T1"}])
        text = recorder.render()
        self.assertIn("KC Works", text)
        self.assertIn("T1", text)

    def test_note_appears_in_rendered_log(self):
        recorder = ProvenanceRecorder(profile="kcuser")
        recorder.note("Birkbeck eprints: failed (connection error)")
        self.assertIn(
            "Birkbeck eprints: failed (connection error)", recorder.render()
        )
```

- [ ] **Step 2: Create stubs and run tests to verify they fail**

`knowledge_commons_profiles/cv_generator/pipeline/dedupe.py` stub:

```python
def normalise_doi(doi):
    raise NotImplementedError


def record_dois(record):
    raise NotImplementedError


def merge_records(primary, secondary, recorder=None):
    raise NotImplementedError
```

`knowledge_commons_profiles/cv_generator/pipeline/provenance.py` stub:

```python
class ProvenanceRecorder:
    def __init__(self, profile=None):
        raise NotImplementedError
```

Run the two new test modules. Expected: every test FAILS with `NotImplementedError`.

- [ ] **Step 3: Copy the implementations and adapt**

```bash
cp $EPRINTSTOCV/cv/dedupe.py knowledge_commons_profiles/cv_generator/pipeline/dedupe.py
cp $EPRINTSTOCV/cv/provenance.py knowledge_commons_profiles/cv_generator/pipeline/provenance.py
```

`dedupe.py` needs no edits (pure stdlib). In `provenance.py`:

1. Fix any `from cv.` imports to `from knowledge_commons_profiles.cv_generator.pipeline.` (read the file; it may have none).
2. Read the file, then: make `_render` public by renaming it to `render` (update the internal call in `write`), and REPLACE the `write(self, path)` method with nothing (delete it — storage is the DB now).
3. Add a `note` method to `ProvenanceRecorder` (place it next to `record_skipped`, following the existing event-storage pattern used by that class — read how `record_skipped` stores and renders its events and mirror it so notes appear in `render()` output under the fetch events):

```python
    def note(self, text):
        """Record a free-text event (e.g. a per-repository fetch failure)."""
```

with a body that appends `text` to the same rendered output. (The exact storage shape depends on the class internals you just read; the behavioural contract is the two tests above.)

- [ ] **Step 4: Run tests to verify they pass**

Run both test modules. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): port dedupe and provenance pipeline modules"
```

---

### Task 5: Pipeline port — identity and eprints sources

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/identity.py`
- Create: `knowledge_commons_profiles/cv_generator/pipeline/sources.py` (copied)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_identity.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_sources.py` (ported)

**Interfaces:**
- Consumes: `CVIdentity` (Task 2), `Profile`.
- Produces:
  - `identity.Identity` dataclass: `name: str`, `emails: list[str]`, `orcid: str`, `kc_username: str`.
  - `identity.resolve_identity(profile) -> Identity` — CVIdentity overrides win field-by-field; emails fall back `CVIdentity.emails → profile.emails → [profile.email]`.
  - `identity.encode_eprints_user(name) -> str` (moved from eprintsToCV `configuration.py`; 'Martin Paul Eve' → 'Eve=3AMartin_Paul=3A=3A').
  - `sources.EprintsSource(config, logger, entry)` with `.fetch() -> list[dict]`, `.name`, settable `.recorder`; `entry = {"repo": hostname, "name": label|None, "search": {"strategies": [...], "mode": ...}|None}`; `config` is any object with `.user`, `.emails` attributes (later tasks pass a `SimpleNamespace`).
  - `sources.ConfigView`, `sources.SourceConfigurationError`, `sources.parse_search_spec`, `sources.normalise_source_entries`, `sources.default_source_name` — unchanged from eprintsToCV.

- [ ] **Step 1: Write the failing identity tests**

`knowledge_commons_profiles/cv_generator/tests/test_pipeline_identity.py`:

```python
"""Identity resolution: profile values with CVIdentity overrides."""

from django.test import TestCase

from knowledge_commons_profiles.cv_generator.models import CVIdentity
from knowledge_commons_profiles.cv_generator.pipeline.identity import (
    encode_eprints_user,
    resolve_identity,
)
from knowledge_commons_profiles.newprofile.models import Profile


class EncodeEprintsUserTests(TestCase):
    def test_encodes_family_name_first(self):
        self.assertEqual(
            encode_eprints_user("Martin Paul Eve"), "Eve=3AMartin_Paul=3A=3A"
        )


class ResolveIdentityTests(TestCase):
    def make_profile(self, **kwargs):
        defaults = {
            "name": "Test User",
            "username": "kcuser",
            "email": "primary@example.org",
            "emails": ["a@example.org", "b@example.org"],
            "orcid": "0000-0001-2345-6789",
        }
        defaults.update(kwargs)
        return Profile.objects.create(**defaults)

    def test_profile_values_used_when_no_overrides(self):
        identity = resolve_identity(self.make_profile())
        self.assertEqual(identity.name, "Test User")
        self.assertEqual(identity.emails, ["a@example.org", "b@example.org"])
        self.assertEqual(identity.orcid, "0000-0001-2345-6789")
        self.assertEqual(identity.kc_username, "kcuser")

    def test_overrides_win_field_by_field(self):
        profile = self.make_profile()
        CVIdentity.objects.create(
            profile=profile, name="Dr Someone Else", emails=[], orcid=""
        )
        identity = resolve_identity(profile)
        self.assertEqual(identity.name, "Dr Someone Else")
        # blank override fields fall back to the profile
        self.assertEqual(identity.emails, ["a@example.org", "b@example.org"])
        self.assertEqual(identity.orcid, "0000-0001-2345-6789")

    def test_single_email_fallback(self):
        identity = resolve_identity(self.make_profile(emails=[]))
        self.assertEqual(identity.emails, ["primary@example.org"])

    def test_no_emails_at_all_yields_empty_list(self):
        identity = resolve_identity(self.make_profile(emails=[], email=""))
        self.assertEqual(identity.emails, [])
```

- [ ] **Step 2: Port the sources tests**

```bash
cp $EPRINTSTOCV/tests/test_sources.py knowledge_commons_profiles/cv_generator/tests/test_pipeline_sources.py
```

Convert per the Task 4 pattern. Also merge in the eprints-relevant tests from `$EPRINTSTOCV/tests/test_search_strategies.py` (the ones exercising `EprintsSource`; Invenio ones move in Task 6). One extra import fix: the ported `sources.py` gets `encode_eprints_user` from `pipeline.identity`, so tests importing it from `cv.configuration` change to `from knowledge_commons_profiles.cv_generator.pipeline.identity import encode_eprints_user`. Any test constructing config objects keeps doing so with `types.SimpleNamespace` (or the file's existing fake-config class). Tests that mock `requests.get` must patch `knowledge_commons_profiles.cv_generator.pipeline.sources.requests.get`.

- [ ] **Step 3: Create stubs and run tests to verify they fail**

`pipeline/identity.py` stub:

```python
import dataclasses


@dataclasses.dataclass
class Identity:
    name: str
    emails: list
    orcid: str
    kc_username: str


def encode_eprints_user(name):
    raise NotImplementedError


def resolve_identity(profile):
    raise NotImplementedError
```

`pipeline/sources.py` stub:

```python
class SourceConfigurationError(ValueError):
    pass


def parse_search_spec(value):
    raise NotImplementedError


def encode_eprints_value(value):
    raise NotImplementedError


def normalise_source_entries(value):
    raise NotImplementedError


def default_source_name(url):
    raise NotImplementedError


class ConfigView:
    def __init__(self, base, **overrides):
        raise NotImplementedError


class EprintsSource:
    def __init__(self, config, logger, entry):
        raise NotImplementedError
```

Run both new test modules. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement**

```bash
cp $EPRINTSTOCV/cv/sources.py knowledge_commons_profiles/cv_generator/pipeline/sources.py
```

Edits to the copied `sources.py`:

1. `from cv.configuration import encode_eprints_user` → `from knowledge_commons_profiles.cv_generator.pipeline.identity import encode_eprints_user`.

`pipeline/identity.py` implementation:

```python
"""Who a CV is for: the profile's identity with per-user overrides."""

import dataclasses


@dataclasses.dataclass
class Identity:
    """The identity used for repository matching and the CV header."""

    name: str
    emails: list
    orcid: str
    kc_username: str


def encode_eprints_user(name):
    """
    Convert a plaintext name to the eprints person-identifier format:
    'Martin Paul Eve' becomes 'Eve=3AMartin_Paul=3A=3A' (the URL-encoded
    form of 'Eve:Martin_Paul::', family name first).
    :param name: the user's name in plain text
    :return: the encoded eprints person identifier
    """
    parts = name.split()
    family = parts[-1]
    given = "_".join(parts[:-1])

    return f"{family}=3A{given}=3A=3A"


def resolve_identity(profile):
    """
    Resolve the identity to build CVs for: CVIdentity overrides win
    field-by-field, blank fields fall back to the profile itself.
    :param profile: a newprofile.Profile
    :return: an Identity
    """
    overrides = getattr(profile, "cv_identity", None)

    name = (overrides.name if overrides else "") or profile.name
    orcid = (overrides.orcid if overrides else "") or profile.orcid

    emails = list(overrides.emails) if overrides and overrides.emails else []
    if not emails:
        emails = list(profile.emails or [])
    if not emails and profile.email:
        emails = [profile.email]

    return Identity(
        name=name,
        emails=emails,
        orcid=orcid,
        kc_username=profile.username,
    )
```

(Note: `getattr(profile, "cv_identity", None)` raises `RelatedObjectDoesNotExist` — a subclass of both `AttributeError` and `ObjectDoesNotExist` — when no row exists, which `getattr` swallows as `AttributeError`. This is the intended fallback path.)

- [ ] **Step 5: Run tests to verify they pass**

Run both test modules. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): port eprints source pipeline and add identity resolution"
```

---

### Task 6: Pipeline port — InvenioRDM source with KC-username strategy

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/invenio.py` (copied + one new strategy)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_invenio.py` (ported + new tests)

**Interfaces:**
- Consumes: `pipeline.sources` (Task 5).
- Produces: `invenio.InvenioSource(config, logger)` with `.fetch() -> list[dict]`, `.name`, settable `.recorder`. `config.invenio` is the entry dict `{"api": url, "name": label|None, "search": spec|None, ...}`; strategies are `'name'`, `'orcid'`, `'query:<raw>'`, and — NEW — `'username'`, which searches `metadata.creators.person_or_org.identifiers.identifier:"<config.kc_username>"` (how KC Works indexes KC usernames; mirrors `newprofile/works.py:385-390`). Also `invenio.DEFAULT_TYPE_MAP`, `invenio.REFEREED_TYPES`.

- [ ] **Step 1: Port tests and add the username-strategy tests (must fail first)**

```bash
cp $EPRINTSTOCV/tests/test_invenio.py knowledge_commons_profiles/cv_generator/tests/test_pipeline_invenio.py
```

Convert per the Task 4 pattern (patch target for HTTP: `knowledge_commons_profiles.cv_generator.pipeline.invenio.requests.get`). Merge in the Invenio-side tests from `$EPRINTSTOCV/tests/test_search_strategies.py`. Then ADD to the converted file:

```python
class UsernameStrategyTests(SimpleTestCase):
    def make_source(self, search=None, kc_username="kcuser"):
        config = SimpleNamespace(
            user="Test User",
            orcid="",
            kc_username=kc_username,
            invenio={
                "api": "https://works.example.org/api/records",
                "search": search,
            },
        )
        return InvenioSource(config, logging.getLogger(__name__))

    def test_username_strategy_queries_the_identifier_field(self):
        source = self.make_source(
            search={"strategies": ["username"], "mode": "first"}
        )
        self.assertEqual(
            source._query_for("username"),
            'metadata.creators.person_or_org.identifiers.identifier:"kcuser"',
        )

    def test_username_strategy_without_username_is_an_error(self):
        source = self.make_source(
            search={"strategies": ["username"], "mode": "first"},
            kc_username="",
        )
        with self.assertRaises(SourceConfigurationError):
            source._query_for("username")
```

(with `import logging`, `from types import SimpleNamespace`, and imports of `InvenioSource`, `SourceConfigurationError` at the top of the file).

- [ ] **Step 2: Create stub and run tests to verify they fail**

`pipeline/invenio.py` stub:

```python
DEFAULT_TYPE_MAP = {}
REFEREED_TYPES = set()


class InvenioSource:
    def __init__(self, config, logger):
        raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError` (and the two new strategy tests fail too).

- [ ] **Step 3: Implement**

```bash
cp $EPRINTSTOCV/cv/invenio.py knowledge_commons_profiles/cv_generator/pipeline/invenio.py
```

Edits:

1. `from cv.sources import (…)` → `from knowledge_commons_profiles.cv_generator.pipeline.sources import (…)` (same names).
2. In `_query_for`, insert the new strategy branch between the `orcid` branch and the `query:` branch:

```python
        if strategy == "username":
            username = getattr(self.config, "kc_username", None)
            if not username:
                raise SourceConfigurationError(
                    f"{self.name}: the 'username' search strategy needs a "
                    "`kc_username` in the configuration"
                )
            return (
                "metadata.creators.person_or_org.identifiers.identifier:"
                f'"{username}"'
            )
```

3. In the error message of the final `raise` in `_query_for`, extend the expected list: `(expected 'name', 'orcid', 'username', or 'query:<raw query>')`.

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): port InvenioRDM source with KC-username search strategy"
```

---

### Task 7: Classification of records into works types

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/classify.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_classify.py`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces:
  - Module constants copied from the reference config (`$EPRINTSTOCV/config/martin_paul_eve.py:50-94, 270-278`), keyed by the Task 2 `WORKS_TYPES` names: `PEER_REVIEWED`, `EDITORIAL`, `BOOK_REVIEW`, `EPRINTS_DB`, `CITEPROC_TYPE_MAPPER` (dicts, exact values from that file), plus `DEFAULT_HEADINGS` = the file's `section_headings['pdf']` dict.
  - `classify(records: list[dict], review_of: str = "Review of") -> dict[str, list[dict]]` — every works type key present, each holding the records that pass the type's peer-review/editorial/book-review filters (same semantics as `$EPRINTSTOCV/cv/repository.py:269-403`).
  - `counts(records, review_of="Review of") -> dict[str, int]` — `len` of each classify bucket.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_pipeline_classify.py`:

```python
"""Classification of merged records into CV works types."""

from django.test import SimpleTestCase

from knowledge_commons_profiles.cv_generator.pipeline.classify import (
    classify,
    counts,
)


def book(**kwargs):
    item = {"type": "book", "title": "A Book", "refereed": "TRUE"}
    item.update(kwargs)
    return item


def article(**kwargs):
    item = {"type": "article", "title": "An Article", "refereed": "TRUE"}
    item.update(kwargs)
    return item


class ClassifyTests(SimpleTestCase):
    def test_authored_book_is_unedited_and_all_books_not_edited(self):
        result = classify([book()])
        self.assertEqual(len(result["unedited_books"]), 1)
        self.assertEqual(len(result["all_books"]), 1)
        self.assertEqual(result["edited_books"], [])

    def test_book_with_editors_is_edited_not_unedited(self):
        result = classify([book(editors=[{"name": {"given": "A", "family": "B"}}])])
        self.assertEqual(len(result["edited_books"]), 1)
        self.assertEqual(result["unedited_books"], [])
        self.assertEqual(len(result["all_books"]), 1)

    def test_refereed_article_is_peer_reviewed_not_other(self):
        result = classify([article()])
        self.assertEqual(len(result["peer_reviewed_articles"]), 1)
        self.assertEqual(result["other_articles"], [])

    def test_unrefereed_article_is_other_not_peer_reviewed(self):
        result = classify([article(refereed="FALSE")])
        self.assertEqual(result["peer_reviewed_articles"], [])
        self.assertEqual(len(result["other_articles"]), 1)

    def test_review_prefix_routes_articles_to_reviews_only(self):
        result = classify([article(title="Review of Something Important")])
        self.assertEqual(len(result["reviews"]), 1)
        # 'reviews' accepts them; the review filter keeps them nowhere else
        # except type-agnostic buckets that allow reviews ("ANY")
        self.assertNotIn(
            "Review of Something Important",
            [i["title"] for i in result["other_articles"]],
        )

    def test_custom_review_prefix_is_honoured(self):
        result = classify(
            [article(title="Rezension: Ein Buch", refereed="FALSE")],
            review_of="Rezension:",
        )
        self.assertEqual(len(result["reviews"]), 1)

    def test_book_section_and_conference_types(self):
        result = classify(
            [
                {"type": "book_section", "title": "C", "refereed": "TRUE"},
                {"type": "conference_item", "title": "D", "refereed": "FALSE"},
            ]
        )
        self.assertEqual(len(result["book_chapters"]), 1)
        self.assertEqual(len(result["conference_items"]), 1)

    def test_unknown_type_is_ignored(self):
        result = classify([{"type": "video", "title": "E"}])
        self.assertTrue(all(len(v) == 0 for v in result.values()))

    def test_every_works_type_key_is_present_even_when_empty(self):
        from knowledge_commons_profiles.cv_generator.models import WORKS_TYPES

        result = classify([])
        self.assertEqual(set(result.keys()), {key for key, _ in WORKS_TYPES})


class CountsTests(SimpleTestCase):
    def test_counts_match_classification(self):
        result = counts([book(), article(), article(refereed="FALSE")])
        self.assertEqual(result["unedited_books"], 1)
        self.assertEqual(result["peer_reviewed_articles"], 1)
        self.assertEqual(result["other_articles"], 1)
```

- [ ] **Step 2: Create stub and run tests to verify they fail**

`pipeline/classify.py` stub:

```python
PEER_REVIEWED = {}
EDITORIAL = {}
BOOK_REVIEW = {}
EPRINTS_DB = {}
CITEPROC_TYPE_MAPPER = {}
DEFAULT_HEADINGS = {}


def classify(records, review_of="Review of"):
    raise NotImplementedError


def counts(records, review_of="Review of"):
    raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

`pipeline/classify.py` — copy the five mapping dicts VERBATIM from `$EPRINTSTOCV/config/martin_paul_eve.py` (`peer_reviewed` lines 50-58 → `PEER_REVIEWED`; `editorial` 61-69 → `EDITORIAL`; `book_review` 75-83 → `BOOK_REVIEW`; `eprints_db` 86-94 → `EPRINTS_DB`; `citeproc_type_mapper` 270-278 → `CITEPROC_TYPE_MAPPER`; `section_headings['pdf']` 28-36 → `DEFAULT_HEADINGS`), then implement classification as a port of `Repository._build_output_types_list` and its three filters (`$EPRINTSTOCV/cv/repository.py:269-403`), with `self.config.X` replaced by the module constants and `self.config.review_of` by the `review_of` parameter:

```python
"""Classify merged repository records into CV works types.

The mappings are the proven defaults from eprintsToCV's reference
configuration; they are deliberately not user-configurable.
"""


def _matches(setting, condition):
    """One three-state filter check: 'ANY' passes everything, True
    requires the condition, False requires its absence."""
    if setting == "ANY":
        return True
    return bool(setting) == bool(condition)


def classify(records, review_of="Review of"):
    """
    Split records into works-type buckets by type and the peer-review,
    editorial, and book-review conditions.
    :param records: merged internal-format records
    :param review_of: the title prefix that marks a book review
    :return: {works_type: [records]}, every known type present
    """
    outputs = {works_type: [] for works_type in EPRINTS_DB}

    for item in records:
        for works_type, db_type in EPRINTS_DB.items():
            if item.get("type") != db_type:
                continue
            if not _matches(
                PEER_REVIEWED[works_type], item.get("refereed") == "TRUE"
            ):
                continue
            if not _matches(EDITORIAL[works_type], "editors" in item):
                continue
            if not _matches(
                BOOK_REVIEW[works_type],
                item.get("title", "").startswith(review_of),
            ):
                continue
            outputs[works_type].append(item)

    return outputs


def counts(records, review_of="Review of"):
    """Per-works-type record counts for the builder UI."""
    return {
        works_type: len(items)
        for works_type, items in classify(records, review_of).items()
    }
```

Note the port simplification: `_matches` compresses the original's three-branch filters; the peer-review filter's original semantics (`refereed == "TRUE"` for True, `refereed == "FALSE"` for False) survive because `_matches(False, item.get("refereed") == "TRUE")` passes items whose refereed is FALSE **or missing** — the original passed only explicit FALSE. If the ported tests expose this difference (records with no `refereed` key), match the original exactly instead:

```python
            refereed = item.get("refereed")
            setting = PEER_REVIEWED[works_type]
            if not (
                setting == "ANY"
                or (setting is True and refereed == "TRUE")
                or (setting is False and refereed == "FALSE")
            ):
                continue
```

Use this exact-port variant — behavioural fidelity to eprintsToCV wins over brevity.

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add works-type classification with eprintsToCV default mappings"
```

---

### Task 8: Fetch orchestration

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/fetch.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_fetch.py`

**Interfaces:**
- Consumes: `CVRepository` (Task 2), `identity.resolve_identity` (Task 5), `sources.EprintsSource/ConfigView` (Task 5), `invenio.InvenioSource` (Task 6), `dedupe.merge_records` + `provenance.ProvenanceRecorder` (Task 4).
- Produces:
  - `fetch.FetchFailed(Exception)` with `.errors: list[tuple[str, str]]` (source name, message).
  - `fetch.fetch_works(profile) -> tuple[list[dict], str]` — (merged records, rendered provenance text). Iterates the profile's `CVRepository` rows in position order (the user's ordering IS the merge precedence — spec deviation from eprintsToCV's eprints-first rule). A failing source is recorded via `provenance.note(...)` and skipped; only if EVERY source fails (or none exist) does it raise `FetchFailed`.
  - `fetch.build_sources(profile, identity, logger) -> list` — one source object per repository row, with unusable strategies dropped (e.g. `orcid` when the identity has no ORCID, `email` when no emails, `username` for non-KC endpoints is kept — it errors only if configured without a username).
  - `fetch.DEFAULT_INVENIO_SEARCH = {"strategies": ["username", "orcid", "name"], "mode": "union"}`, `fetch.DEFAULT_EPRINTS_SEARCH = {"strategies": ["name"], "mode": "first"}`.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_pipeline_fetch.py`:

```python
"""Fetch orchestration: DB-configured sources, merge, tolerant failure."""

import logging
from unittest import mock

import requests
from django.test import TestCase

from knowledge_commons_profiles.cv_generator.models import CVRepository
from knowledge_commons_profiles.cv_generator.pipeline import fetch
from knowledge_commons_profiles.cv_generator.pipeline.fetch import (
    FetchFailed,
    build_sources,
    fetch_works,
)
from knowledge_commons_profiles.cv_generator.pipeline.identity import (
    resolve_identity,
)
from knowledge_commons_profiles.newprofile.models import Profile

LOGGER = logging.getLogger(__name__)


def make_profile(orcid="0000-0001-2345-6789"):
    return Profile.objects.create(
        name="Test User", username="kcuser", orcid=orcid,
        emails=["a@example.org"],
    )


def add_invenio(profile, position=0, **kwargs):
    defaults = {
        "kind": CVRepository.KIND_INVENIO,
        "endpoint": "https://works.example.org/api/records",
        "label": "KC Works",
        "position": position,
    }
    defaults.update(kwargs)
    return CVRepository.objects.create(profile=profile, **defaults)


def add_eprints(profile, position=1, **kwargs):
    defaults = {
        "kind": CVRepository.KIND_EPRINTS,
        "endpoint": "eprints.example.org",
        "label": "Example eprints",
        "position": position,
    }
    defaults.update(kwargs)
    return CVRepository.objects.create(profile=profile, **defaults)


class BuildSourcesTests(TestCase):
    def test_sources_follow_repository_position_order(self):
        profile = make_profile()
        add_eprints(profile, position=2)
        add_invenio(profile, position=1)
        sources = build_sources(profile, resolve_identity(profile), LOGGER)
        self.assertEqual([s.name for s in sources],
                         ["KC Works", "Example eprints"])

    def test_orcid_strategy_dropped_when_identity_has_no_orcid(self):
        profile = make_profile(orcid="")
        add_invenio(
            profile,
            search_config={"strategies": ["username", "orcid"],
                           "mode": "union"},
        )
        (source,) = build_sources(profile, resolve_identity(profile), LOGGER)
        strategies, _mode = source._search_plan()
        self.assertEqual(strategies, ["username"])

    def test_default_invenio_search_is_username_orcid_name_union(self):
        profile = make_profile()
        add_invenio(profile)
        (source,) = build_sources(profile, resolve_identity(profile), LOGGER)
        strategies, mode = source._search_plan()
        self.assertEqual(strategies, ["username", "orcid", "name"])
        self.assertEqual(mode, "union")


class FetchWorksTests(TestCase):
    def test_merges_sources_in_position_order(self):
        profile = make_profile()
        add_invenio(profile, position=1)
        add_eprints(profile, position=2)

        primary = [{"type": "book", "title": "Shared", "doi": "10.1/x"}]
        secondary = [
            {"type": "book", "title": "Shared", "doi": "10.1/x",
             "publisher": "P"},
            {"type": "article", "title": "Only Here", "refereed": "TRUE"},
        ]

        with mock.patch.object(
            fetch, "build_sources"
        ) as build:
            one = mock.Mock(name_attr="KC Works")
            one.name = "KC Works"
            one.fetch.return_value = primary
            two = mock.Mock()
            two.name = "Example eprints"
            two.fetch.return_value = secondary
            build.return_value = [one, two]

            records, provenance_text = fetch_works(profile)

        titles = [r["title"] for r in records]
        self.assertEqual(titles, ["Shared", "Only Here"])
        # gap-filling from the secondary copy
        self.assertEqual(records[0]["publisher"], "P")
        self.assertIn("KC Works", provenance_text)

    def test_one_failing_source_is_skipped_and_noted(self):
        profile = make_profile()
        add_invenio(profile, position=1)
        add_eprints(profile, position=2)

        with mock.patch.object(fetch, "build_sources") as build:
            bad = mock.Mock()
            bad.name = "KC Works"
            bad.fetch.side_effect = requests.ConnectionError("boom")
            good = mock.Mock()
            good.name = "Example eprints"
            good.fetch.return_value = [{"type": "book", "title": "B"}]
            build.return_value = [bad, good]

            records, provenance_text = fetch_works(profile)

        self.assertEqual([r["title"] for r in records], ["B"])
        self.assertIn("KC Works", provenance_text)
        self.assertIn("failed", provenance_text)

    def test_all_sources_failing_raises_fetch_failed(self):
        profile = make_profile()
        add_invenio(profile)

        with mock.patch.object(fetch, "build_sources") as build:
            bad = mock.Mock()
            bad.name = "KC Works"
            bad.fetch.side_effect = requests.ConnectionError("boom")
            build.return_value = [bad]

            with self.assertRaises(FetchFailed) as caught:
                fetch_works(profile)

        self.assertEqual(caught.exception.errors[0][0], "KC Works")

    def test_no_repositories_raises_fetch_failed(self):
        profile = make_profile()
        with self.assertRaises(FetchFailed):
            fetch_works(profile)
```

- [ ] **Step 2: Create stub and run tests to verify they fail**

`pipeline/fetch.py` stub:

```python
DEFAULT_INVENIO_SEARCH = {"strategies": ["username", "orcid", "name"],
                          "mode": "union"}
DEFAULT_EPRINTS_SEARCH = {"strategies": ["name"], "mode": "first"}


class FetchFailed(Exception):
    def __init__(self, errors):
        super().__init__(str(errors))
        self.errors = errors


def build_sources(profile, identity, logger):
    raise NotImplementedError


def fetch_works(profile):
    raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

`pipeline/fetch.py`:

```python
"""Fetch a profile's works from its configured repositories.

This is the DB-backed replacement for eprintsToCV's Repository fetch
path: repositories come from CVRepository rows instead of a config
module, the user's position ordering fully governs merge precedence,
and a failing repository is skipped (and noted in the provenance log)
rather than aborting the whole fetch.
"""

import json
import logging
from types import SimpleNamespace

import requests

from knowledge_commons_profiles.cv_generator.models import CVRepository
from knowledge_commons_profiles.cv_generator.pipeline.dedupe import (
    merge_records,
)
from knowledge_commons_profiles.cv_generator.pipeline.invenio import (
    InvenioSource,
)
from knowledge_commons_profiles.cv_generator.pipeline.provenance import (
    ProvenanceRecorder,
)
from knowledge_commons_profiles.cv_generator.pipeline.sources import (
    ConfigView,
    EprintsSource,
    SourceConfigurationError,
)

logger = logging.getLogger(__name__)

DEFAULT_INVENIO_SEARCH = {"strategies": ["username", "orcid", "name"],
                          "mode": "union"}
DEFAULT_EPRINTS_SEARCH = {"strategies": ["name"], "mode": "first"}

# what each strategy needs from the identity to be runnable
_STRATEGY_NEEDS = {
    "orcid": lambda identity: bool(identity.orcid),
    "email": lambda identity: bool(identity.emails),
    "name": lambda identity: bool(identity.name),
    "username": lambda identity: bool(identity.kc_username),
}


class FetchFailed(Exception):
    """Every configured repository failed (or none are configured)."""

    def __init__(self, errors):
        super().__init__(
            "; ".join(f"{name}: {message}" for name, message in errors)
            or "no repositories configured"
        )
        self.errors = errors


def _usable_search(repository, identity):
    """The repository's search spec with unusable strategies dropped."""
    default = (
        DEFAULT_EPRINTS_SEARCH
        if repository.kind == CVRepository.KIND_EPRINTS
        else DEFAULT_INVENIO_SEARCH
    )
    configured = repository.search_config or default
    strategies = [
        strategy
        for strategy in configured.get("strategies", [])
        if _STRATEGY_NEEDS.get(
            strategy.split(":", 1)[0], lambda identity: True
        )(identity)
    ]

    if not strategies:
        return None

    return {
        "strategies": strategies,
        "mode": configured.get("mode", "union"),
    }


def build_sources(profile, identity, logger):
    """One fetchable source object per configured repository, in the
    user's position order."""
    config = SimpleNamespace(
        user=identity.name,
        emails=identity.emails,
        orcid=identity.orcid,
        kc_username=identity.kc_username,
    )

    sources = []
    for repository in profile.cv_repositories.all():
        search = _usable_search(repository, identity)
        if search is None:
            logger.warning(
                "No usable search strategies for %s; skipping",
                repository.label or repository.endpoint,
            )
            continue

        entry = {"search": search}
        if repository.label:
            entry["name"] = repository.label

        if repository.kind == CVRepository.KIND_EPRINTS:
            entry["repo"] = repository.endpoint
            sources.append(EprintsSource(config, logger, entry))
        else:
            entry["api"] = repository.endpoint
            sources.append(
                InvenioSource(ConfigView(config, invenio=entry), logger)
            )

    return sources


def fetch_works(profile):
    """
    Fetch and merge the profile's works from every configured repository.
    :param profile: a newprofile.Profile
    :return: (merged record list, rendered provenance text)
    :raises FetchFailed: when no repository yields records
    """
    from knowledge_commons_profiles.cv_generator.pipeline.identity import (
        resolve_identity,
    )

    identity = resolve_identity(profile)
    provenance = ProvenanceRecorder(profile=profile.username)
    sources = build_sources(profile, identity, logger)

    records = None
    errors = []

    for source in sources:
        source.recorder = provenance
        try:
            items = source.fetch()
        except (
            requests.RequestException,
            json.JSONDecodeError,
            SourceConfigurationError,
        ) as exc:
            logger.warning("Error fetching from %s: %s", source.name, exc)
            errors.append((source.name, str(exc)))
            provenance.note(f"{source.name}: failed ({exc})")
            continue

        if records is None:
            records = items
            provenance.base_records(source.name, items)
        else:
            records = merge_records(
                records, items, recorder=provenance.for_source(source.name)
            )

    if records is None:
        raise FetchFailed(errors)

    return records, provenance.render()
```

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS. (If `test_orcid_strategy_dropped…` fails because `_search_plan` is a private name that moved, adjust the test to call the public behaviour instead: run `source.fetch()` with `requests.get` mocked and assert only the username query was issued.)

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add DB-backed fetch orchestration with tolerant per-repository failure"
```

---

### Task 9: Citation engine port and vendored assets

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/js/citeproc_commonjs.js` (vendored)
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/js/CITEPROC-LICENSE` (vendored)
- Create: `knowledge_commons_profiles/cv_generator/pipeline/citeproc_engine.py` (copied)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_citeproc_engine.py` (ported)
- Modify: `pyproject.toml` (add `mini-racer`)

**Interfaces:**
- Consumes: `settings.CITATION_STYLES` (name → path relative to `knowledge_commons_profiles/citeproc/data/`, some without the `.csl` suffix, e.g. `"Harvard": "harvard1"`); CSL styles and locales already vendored in `knowledge_commons_profiles/citeproc/data/{styles,locales}`.
- Produces:
  - `citeproc_engine.CitationRenderer(logger, locale="en-GB")` with `.render(items: list[dict], style: str, link_titles=False) -> list[str]` — `style` is a `CITATION_STYLES` KEY (e.g. `"MHRA"`), resolved internally; results cached per (style, link_titles, item-content).
  - `citeproc_engine.CiteprocEngine(style_path, locale_path)` — unchanged from eprintsToCV.
  - `citeproc_engine.style_path(style_key) -> Path` and `citeproc_engine.locale_path(locale) -> Path` (module functions; raise `KeyError` for unknown style keys, `FileNotFoundError` if the resolved file is missing).

- [ ] **Step 1: Vendor the assets and add the dependency**

```bash
mkdir -p knowledge_commons_profiles/cv_generator/static/cv_generator/js
cp $EPRINTSTOCV/static/js/citeproc_commonjs.js knowledge_commons_profiles/cv_generator/static/cv_generator/js/
cp $EPRINTSTOCV/static/js/CITEPROC-LICENSE knowledge_commons_profiles/cv_generator/static/cv_generator/js/
uv add mini-racer
```

(If `uv add mini-racer` fails to resolve, the PyPI name used by eprintsToCV is in `$EPRINTSTOCV/pyproject.toml` — use exactly that name/version.)

- [ ] **Step 2: Port tests and add path-resolution tests (must fail first)**

```bash
cp $EPRINTSTOCV/tests/test_renderer.py knowledge_commons_profiles/cv_generator/tests/test_pipeline_citeproc_engine.py
```

Convert per the Task 4 pattern; imports come from `…pipeline.citeproc_engine`. Where the original tests pass a config object carrying `csl_directory`/`citeproc_locale`, rewrite the construction to `CitationRenderer(logging.getLogger(__name__))` and pass style KEY `"MHRA"` wherever the original passed the style name `"modern-humanities-research-association"`. ADD:

```python
class StylePathTests(SimpleTestCase):
    def test_mhra_resolves_to_existing_csl_file(self):
        path = style_path("MHRA")
        self.assertTrue(str(path).endswith(
            "styles/modern-humanities-research-association.csl"))
        self.assertTrue(path.exists())

    def test_harvard_suffixless_setting_resolves(self):
        path = style_path("Harvard")
        self.assertTrue(str(path).endswith("harvard1.csl"))
        self.assertTrue(path.exists())

    def test_unknown_style_key_raises(self):
        with self.assertRaises(KeyError):
            style_path("NotAStyle")

    def test_locale_path_resolves(self):
        self.assertTrue(locale_path("en-GB").exists())
```

Also add one golden rendering test (real mini-racer, no network):

```python
class RenderSmokeTests(SimpleTestCase):
    def test_renders_a_book_in_mhra(self):
        renderer = CitationRenderer(logging.getLogger(__name__))
        (entry,) = renderer.render(
            [{
                "title": "Open Access and the Humanities",
                "type": "book",
                "issued": {"date-parts": [[2014]]},
                "author": [{"family": "Eve", "given": "Martin Paul"}],
                "publisher": "Cambridge University Press",
                "publisher-place": "Cambridge",
            }],
            "MHRA",
        )
        self.assertIn("Open Access and the Humanities", entry)
        self.assertIn("Eve", entry)
        self.assertIn("2014", entry)
```

- [ ] **Step 3: Create stub and run tests to verify they fail**

`pipeline/citeproc_engine.py` stub:

```python
def style_path(style_key):
    raise NotImplementedError


def locale_path(locale):
    raise NotImplementedError


class CiteprocEngine:
    def __init__(self, style_path, locale_path):
        raise NotImplementedError


class CitationRenderer:
    def __init__(self, logger, locale="en-GB"):
        raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement**

```bash
cp $EPRINTSTOCV/cv/renderer.py knowledge_commons_profiles/cv_generator/pipeline/citeproc_engine.py
```

Edits to the copied file:

1. Replace the module-path constants at the top:

```python
from pathlib import Path

from django.conf import settings

APP_DIR = Path(__file__).resolve().parents[1]
CITEPROC_PATH = APP_DIR / "static" / "cv_generator" / "js" / "citeproc_commonjs.js"
CSL_DATA_DIR = (
    Path(settings.BASE_DIR) / "knowledge_commons_profiles" / "citeproc" / "data"
)
```

(Check how other modules in this project locate `BASE_DIR`; if `settings.BASE_DIR` isn't defined, use `Path(knowledge_commons_profiles.citeproc.__file__).parent / "data"` with `import knowledge_commons_profiles.citeproc`.)

2. Add module functions (above the classes):

```python
def style_path(style_key):
    """The on-disk CSL file for a CITATION_STYLES key (e.g. 'MHRA')."""
    relative = settings.CITATION_STYLES[style_key]
    path = CSL_DATA_DIR / relative
    if not path.suffix:
        path = path.with_suffix(".csl")
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def locale_path(locale):
    """The on-disk CSL locale file for a locale code (e.g. 'en-GB')."""
    path = CSL_DATA_DIR / "locales" / f"locales-{locale}.xml"
    if not path.exists():
        raise FileNotFoundError(path)
    return path
```

3. Rework `CitationRenderer.__init__` and its path methods: signature becomes `def __init__(self, logger, locale="en-GB")`; delete `self.config`; store `self.locale = locale`. Replace its `style_path`/`locale_path` methods with calls to the module functions (`style_path(style)` where `style` is now the key; `locale_path(self.locale)`). `CiteprocEngine` itself is unchanged apart from the `CITEPROC_PATH` constant now being a `Path` (wrap `open(CITEPROC_PATH)` args in `str()` only if needed — `open` accepts `Path`).

- [ ] **Step 5: Run tests to verify they pass**

Run the test module. Expected: PASS (this exercises real mini-racer + the vendored citeproc-js and CSL files; no network).

- [ ] **Step 6: Commit**

```bash
git add knowledge_commons_profiles/cv_generator pyproject.toml uv.lock
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): port citeproc-js citation engine with project CSL styles"
```

---

### Task 10: CSL conversion and publications-section rendering

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/csl.py`
- Create: `knowledge_commons_profiles/cv_generator/pipeline/sections.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_csl.py` (ported subset)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_sections.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/data/golden_citations.json` (copied)

**Interfaces:**
- Consumes: `classify.CITEPROC_TYPE_MAPPER` (Task 7), `CitationRenderer` (Task 9), `CurriculumVitae`/`WORKS_TYPES` (Task 2).
- Produces:
  - `csl.RenderOptions` dataclass: `citation_style: str` (key), `citation_locale: str`, `citation_link: str` ("title"/"entry"), `gold_oa_direct_link: bool`, `review_of: str`, `titles_to_italicize: list[str]`, `exclude_venues: dict[str, str]`; classmethod `RenderOptions.from_cv(cv) -> RenderOptions` (splits the CV's textarea into a list, line per title, blanks dropped).
  - `csl.build_csl_item(item: dict, counter: int, works_type: str, year, options) -> dict` — a port of `CiteProc._build_csl_item` and its `_build_*` helpers (`$EPRINTSTOCV/cv/citeproc.py:391-605`) with `self.config.X` lookups replaced: `citeproc_type_mapper` → `classify.CITEPROC_TYPE_MAPPER[works_type]`; creators/editors field names hardcoded to the eprintsToCV defaults (`creators`/`editors`, `name`, `given`, `family`); gold-OA URI rewriting governed by `options.gold_oa_direct_link`.
  - `csl.build_year(item) -> int | "n.d."` (port of `_build_date`).
  - `csl.italicize(title: str, options) -> str` (port of `_italicize_titles`, operating on and returning the string).
  - `sections.render_publications_section(items: list[dict], works_type: str, heading: str, options: RenderOptions, renderer: CitationRenderer) -> str` — full `<section>` HTML: heading with count, `<ul class="publist">`, year-in-margin items (new-date vs same-date templates), venue exclusion, title italicization, empty list → `""`. Template constants are the PDF variants from `$EPRINTSTOCV/config/martin_paul_eve.py:128-143, 244-267` (`SECTION_TEMPLATE`, `HEADER_TEMPLATE`, `LIST_TEMPLATE`, `ITEM_TEMPLATE`, `ITEM_TEMPLATE_NEW_DATE`). No OA-status markup (the reference PDF rule has none).

- [ ] **Step 1: Write the failing tests**

Copy the golden fixtures:

```bash
mkdir -p knowledge_commons_profiles/cv_generator/tests/data
cp $EPRINTSTOCV/tests/golden_citations.json knowledge_commons_profiles/cv_generator/tests/data/
```

`test_pipeline_csl.py` — port the CSL-conversion tests from `$EPRINTSTOCV/tests/test_citeproc.py` (only those exercising `_build_csl_item`/`_build_date`/italicization/DOI derivation — the template/output-file tests do NOT port; their replacement is `test_pipeline_sections.py` and Task 11). Conversion notes: calls like `citeproc._build_csl_item(item, 0, section, year, rule)` become `build_csl_item(item, 0, works_type, year, options)` with `options = RenderOptions(citation_style="MHRA", citation_locale="en-GB", citation_link="title", gold_oa_direct_link=True, review_of="Review of", titles_to_italicize=[], exclude_venues={})`. Golden-citation tests that drive the full render pipeline move to `test_pipeline_sections.py` below. Plus new options tests:

```python
class RenderOptionsTests(TestCase):
    def test_from_cv_reads_all_fields(self):
        profile = Profile.objects.create(name="U", username="u1")
        cv = CurriculumVitae.objects.create(
            profile=profile,
            citation_style="MHRA",
            citation_locale="en-GB",
            citation_link="entry",
            gold_oa_direct_link=False,
            review_of="Review of",
            titles_to_italicize="Cloud Atlas\n\n2666\n",
            exclude_venues={"other_articles": "eve.gd"},
        )
        options = RenderOptions.from_cv(cv)
        self.assertEqual(options.citation_link, "entry")
        self.assertFalse(options.gold_oa_direct_link)
        self.assertEqual(options.titles_to_italicize, ["Cloud Atlas", "2666"])
        self.assertEqual(options.exclude_venues, {"other_articles": "eve.gd"})
```

`test_pipeline_sections.py`:

```python
"""Publications-section HTML assembly."""

import logging

from django.test import SimpleTestCase

from knowledge_commons_profiles.cv_generator.pipeline.citeproc_engine import (
    CitationRenderer,
)
from knowledge_commons_profiles.cv_generator.pipeline.csl import RenderOptions
from knowledge_commons_profiles.cv_generator.pipeline.sections import (
    render_publications_section,
)


def options(**kwargs):
    defaults = {
        "citation_style": "MHRA",
        "citation_locale": "en-GB",
        "citation_link": "title",
        "gold_oa_direct_link": True,
        "review_of": "Review of",
        "titles_to_italicize": [],
        "exclude_venues": {},
    }
    defaults.update(kwargs)
    return RenderOptions(**defaults)


def book(title="A Book", year="2020", **kwargs):
    item = {
        "type": "book",
        "title": title,
        "date": year,
        "refereed": "TRUE",
        "uri": "https://example.org/record/1",
        "creators": [{"name": {"given": "Ann", "family": "Author"}}],
        "publisher": "P Press",
    }
    item.update(kwargs)
    return item


class RenderPublicationsSectionTests(SimpleTestCase):
    def setUp(self):
        self.renderer = CitationRenderer(logging.getLogger(__name__))

    def test_empty_items_render_nothing(self):
        html = render_publications_section(
            [], "unedited_books", "BOOKS", options(), self.renderer
        )
        self.assertEqual(html, "")

    def test_section_carries_heading_count_and_list(self):
        html = render_publications_section(
            [book(), book(title="Another Book", year="2019")],
            "unedited_books", "BOOKS", options(), self.renderer,
        )
        self.assertIn("BOOKS (2)", html)
        self.assertIn('<ul class="publist">', html)
        self.assertIn("A Book", html)
        self.assertIn("Another Book", html)
        self.assertIn('aria-labelledby="unedited_books-heading"', html)

    def test_year_appears_once_per_new_year(self):
        html = render_publications_section(
            [book(year="2020"), book(title="Second", year="2020"),
             book(title="Third", year="2019")],
            "unedited_books", "BOOKS", options(), self.renderer,
        )
        # one visible 2020 prefix, one 2019 prefix
        self.assertEqual(html.count('class="prefix bold"'), 2)

    def test_title_link_mode_links_titles(self):
        html = render_publications_section(
            [book()], "unedited_books", "BOOKS",
            options(citation_link="title"), self.renderer,
        )
        self.assertIn('<a href="https://example.org/record/1">', html)

    def test_excluded_venue_is_dropped_and_uncounted(self):
        article = {
            "type": "article", "title": "Post", "date": "2021",
            "refereed": "FALSE", "uri": "https://example.org/2",
            "publication": "eve.gd",
            "creators": [{"name": {"given": "A", "family": "B"}}],
        }
        html = render_publications_section(
            [article], "other_articles", "OTHER",
            options(exclude_venues={"other_articles": "eve.gd"}),
            self.renderer,
        )
        self.assertEqual(html, "")

    def test_italicized_title_survives_citation_rendering(self):
        html = render_publications_section(
            [book(title="Reading Cloud Atlas Closely")],
            "unedited_books", "BOOKS",
            options(titles_to_italicize=["Cloud Atlas"]), self.renderer,
        )
        self.assertIn("<i>Cloud Atlas</i>", html)
```

Port the golden-citations test as the fidelity pin (adapting the original's harness in `$EPRINTSTOCV/tests/test_citeproc.py` — read it first; it feeds each fixture item through CSL conversion + the renderer and compares to the stored entry):

```python
class GoldenCitationTests(SimpleTestCase):
    """Rendered citations must match the eprintsToCV golden outputs."""

    def test_golden_citations_render_identically(self):
        fixture = json.loads(
            (Path(__file__).parent / "data" / "golden_citations.json")
            .read_text()
        )
        renderer = CitationRenderer(logging.getLogger(__name__))
        # mirror the original harness: whatever structure the fixture
        # has (read it!), convert each input item via build_csl_item and
        # assert the rendered entry equals the stored golden string
        for case in fixture_cases(fixture):
            with self.subTest(title=case.title):
                self.assertEqual(render_one(case, renderer), case.expected)
```

(Write `fixture_cases`/`render_one` to match the actual fixture shape found in the JSON — this is deliberately left to the implementer because it must mirror the file's real structure; the assertion contract is exact string equality with the goldens. If a golden depends on eprintsToCV-only config like custom creator field names, drop that case with a comment.)

- [ ] **Step 2: Create stubs and run tests to verify they fail**

`pipeline/csl.py` stub:

```python
import dataclasses


@dataclasses.dataclass
class RenderOptions:
    citation_style: str
    citation_locale: str
    citation_link: str
    gold_oa_direct_link: bool
    review_of: str
    titles_to_italicize: list
    exclude_venues: dict

    @classmethod
    def from_cv(cls, cv):
        raise NotImplementedError


def build_year(item):
    raise NotImplementedError


def italicize(title, options):
    raise NotImplementedError


def build_csl_item(item, counter, works_type, year, options):
    raise NotImplementedError
```

`pipeline/sections.py` stub:

```python
def render_publications_section(items, works_type, heading, options, renderer):
    raise NotImplementedError
```

Run both test modules. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement csl.py**

Port from `$EPRINTSTOCV/cv/citeproc.py` as module functions. The `_build_*` helpers (`_build_creators`, `_build_editors`, `_build_publisher`, `_build_container`, `_build_volume`, `_build_pages`, `_build_event`, `_derive_doi`, `_build_date`, `_build_precise_date`) port with these mechanical substitutions:

- `self.config.creators_item_name` → `"creators"`; `self.config.creator_field_top_level` → `"name"`; `…given_name` → `"given"`; `…last_name` → `"family"`; same for editors.
- `self.config.citeproc_type_mapper[section]` → `CITEPROC_TYPE_MAPPER[works_type]` (import from `.classify`).
- `_build_identifier`'s gold-OA rewrite (`_link_to_official_url_if_gold_oa`) keeps its logic but tests `options.gold_oa_direct_link` instead of `self.config.gold_oa_direct_link[rule]`, mutating `item["uri"]` exactly as the original does.
- `_italicize_titles` becomes `italicize(title, options) -> str`: same regex construction over `options.titles_to_italicize` (cache the compiled regexen on the options object via `functools.lru_cache`-free simple attribute, or rebuild per call — correctness first), returning the new string instead of mutating the item.
- `RenderOptions.from_cv`:

```python
    @classmethod
    def from_cv(cls, cv):
        return cls(
            citation_style=cv.citation_style,
            citation_locale=cv.citation_locale,
            citation_link=cv.citation_link,
            gold_oa_direct_link=cv.gold_oa_direct_link,
            review_of=cv.review_of,
            titles_to_italicize=[
                line.strip()
                for line in cv.titles_to_italicize.splitlines()
                if line.strip()
            ],
            exclude_venues=dict(cv.exclude_venues or {}),
        )
```

- [ ] **Step 4: Implement sections.py**

Port of `CiteProc._eprint_substitute` + `_append_item` + `_substitute_item_template` + `_finalize_section` (`$EPRINTSTOCV/cv/citeproc.py:278-497`), with the config templates as constants (the PDF variants, verbatim from `$EPRINTSTOCV/config/martin_paul_eve.py`):

```python
"""Assemble a publications block into a CV <section>."""

from knowledge_commons_profiles.cv_generator.pipeline.csl import (
    build_csl_item,
    build_year,
    italicize,
)

SECTION_TEMPLATE = '<section id="{0}" aria-labelledby="{2}">{1}</section>'
HEADER_TEMPLATE = '<h2 id="{2}" class="sectionheader">{0} ({1})</h2>'
LIST_TEMPLATE = '<ul class="publist">{0}</ul>'

ITEM_TEMPLATE = (
    '<li class="anitem genericitem"><span class="prefix" '
    'aria-hidden="true">&nbsp;</span><span class="bibitem">'
    "[[citeproc]]</span></li>"
)

ITEM_TEMPLATE_NEW_DATE = (
    '<li class="anitemnewdate genericitem"><span '
    'class="prefix bold" aria-hidden="true">[[year]]</span>'
    '<span class="bibitem">[[citeproc]]</span></li>'
)


def _substitute_item(template, citeproc, year, item, link_mode):
    if link_mode == "title":
        citeproc = citeproc.replace("<div", "<span").replace("</div", "</span")
    else:
        citeproc = citeproc.replace(
            "<div", '<a href="{}"'.format(item.get("uri", ""))
        ).replace("</div", "</a")

    return template.replace("[[citeproc]]", citeproc).replace(
        "[[year]]", str(year)
    )


def render_publications_section(items, works_type, heading, options, renderer):
    """
    Render one publications block as a complete <section>.
    :param items: the classified records for this works type
    :param works_type: the works-type machine name (section/anchor id)
    :param heading: the display heading (block's own, or the default)
    :param options: a RenderOptions
    :param renderer: a CitationRenderer
    :return: HTML, or "" when no items survive exclusion
    """
    excluded = options.exclude_venues.get(works_type, "")
    exclude_venues = [v.strip() for v in excluded.split(",") if v.strip()]

    kept, years, csl_items = [], [], []
    for item in items:
        if item.get("publication") in exclude_venues:
            continue
        item = dict(item)
        item["title"] = italicize(item["title"], options)
        year = build_year(item)
        csl_items.append(
            build_csl_item(item, len(csl_items), works_type, year, options)
        )
        kept.append(item)
        years.append(year)

    if not kept:
        return ""

    entries = renderer.render(
        csl_items,
        options.citation_style,
        link_titles=options.citation_link == "title",
    )

    output, current_year = "", None
    for item, entry, year in zip(kept, entries, years, strict=True):
        if not entry:
            continue
        template = (
            ITEM_TEMPLATE_NEW_DATE if year != current_year else ITEM_TEMPLATE
        )
        current_year = year
        output += _substitute_item(
            template, entry, year, item, options.citation_link
        )

    heading_id = f"{works_type}-heading"
    header = HEADER_TEMPLATE.format(heading, len(kept), heading_id)
    body = LIST_TEMPLATE.format(output)

    return SECTION_TEMPLATE.format(works_type, header + body, heading_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run both test modules. Expected: PASS, including the golden citations.

- [ ] **Step 6: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add CSL conversion and publications-section rendering"
```

---

### Task 11: Document rendering — header, rich text, footer, full HTML

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/document.py`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/pdf_document.html`
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/pagedjs.js` (vendored)
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/pagedjs.css` (vendored)
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/cv.css` (vendored)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_document.py`

**Interfaces:**
- Consumes: `CVBlock`/`CurriculumVitae` (Task 2), `identity.resolve_identity` (Task 5), `classify.classify`/`DEFAULT_HEADINGS` (Task 7), `sections.render_publications_section` (Task 10), `CitationRenderer` (Task 9), `CVWorksStore.records`, `newprofile.utils.sanitize_html`.
- Produces:
  - `document.render_header(identity, profile) -> str` — the PersonInfo-style block: `<h1>` name, *Curriculum Vitae* line, `profile.title` and `profile.affiliation` lines when present, one `<p>` mailto link per email, ORCID link when present. All values HTML-escaped.
  - `document.render_richtext(block) -> str` — `<section class="section">` with optional `<h2 class="sectionheader">` and the sanitized content; empty content AND empty heading → `""`.
  - `document.render_footer(block, generated_at) -> str` — like richtext, plus `<p class="cv-last-updated">Last updated <j F Y></p>` when `block.show_last_updated`.
  - `document.render_document(cv) -> str` — the complete Paged.js HTML: iterates `cv.blocks.all()`, dispatches by kind (publications blocks pull their items from `classify(store.records, options.review_of)[block.works_type]`, heading = `block.heading or DEFAULT_HEADINGS[works_type]`), joins the sections, and renders `cv_generator/pdf_document.html` with context `{"title": …, "body": …}`. Missing works store → publications blocks render `""`.

- [ ] **Step 1: Vendor the Paged.js assets**

```bash
mkdir -p knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs
cp $EPRINTSTOCV/static/pagedJS/js/pagedjs.js knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/
cp $EPRINTSTOCV/static/pagedJS/css/pagedjs.css knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/
cp $EPRINTSTOCV/static/pagedJS/css/cv.css knowledge_commons_profiles/cv_generator/static/cv_generator/pagedjs/
```

Then open the copied `cv.css` and check its `font-family` declarations: if they name Typekit-only families (e.g. `futura-pt`), append system fallbacks (`, Futura, "Century Gothic", Arial, sans-serif` for geometric sans; `, Georgia, serif` for serifs) so the render degrades gracefully without Adobe Fonts. Do not remove the original family names.

- [ ] **Step 2: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_pipeline_document.py`:

```python
"""Full-document HTML assembly from CV blocks."""

from django.test import TestCase
from django.utils import timezone

from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.cv_generator.pipeline.document import (
    render_document,
    render_footer,
    render_header,
    render_richtext,
)
from knowledge_commons_profiles.cv_generator.pipeline.identity import (
    resolve_identity,
)
from knowledge_commons_profiles.newprofile.models import Profile


def make_profile(**kwargs):
    defaults = {
        "name": "Test User", "username": "kcuser",
        "title": "Senior Lecturer", "affiliation": "Example University",
        "emails": ["a@example.org"], "orcid": "0000-0001-2345-6789",
    }
    defaults.update(kwargs)
    return Profile.objects.create(**defaults)


class RenderHeaderTests(TestCase):
    def test_header_contains_identity_details(self):
        profile = make_profile()
        html = render_header(resolve_identity(profile), profile)
        self.assertIn("Test User", html)
        self.assertIn("Curriculum Vitae", html)
        self.assertIn("Senior Lecturer", html)
        self.assertIn("Example University", html)
        self.assertIn('href="mailto:a@example.org"', html)
        self.assertIn("https://orcid.org/0000-0001-2345-6789", html)

    def test_header_escapes_html_in_names(self):
        profile = make_profile(name="<script>x</script>", username="esc")
        identity = resolve_identity(profile)
        html = render_header(identity, profile)
        self.assertNotIn("<script>", html)

    def test_missing_orcid_and_title_are_omitted(self):
        profile = make_profile(orcid="", title=None, username="bare")
        html = render_header(resolve_identity(profile), profile)
        self.assertNotIn("orcid", html.lower())


class RenderRichtextTests(TestCase):
    def make_block(self, **kwargs):
        cv = CurriculumVitae.objects.create(profile=make_profile())
        defaults = {"cv": cv, "kind": CVBlock.KIND_RICHTEXT, "position": 1}
        defaults.update(kwargs)
        return CVBlock.objects.create(**defaults)

    def test_heading_and_content_render(self):
        html = render_richtext(
            self.make_block(heading="Education", content="<p>BA, 2001</p>")
        )
        self.assertIn("Education", html)
        self.assertIn("BA, 2001", html)

    def test_script_content_is_sanitized_at_render_time(self):
        html = render_richtext(
            self.make_block(content='<p>ok</p><script>evil()</script>')
        )
        self.assertNotIn("<script>", html)
        self.assertIn("ok", html)

    def test_empty_block_renders_nothing(self):
        self.assertEqual(self.make_block(heading="", content="").__class__,
                         CVBlock)  # sanity
        self.assertEqual(
            render_richtext(self.make_block(heading="", content="")), ""
        )


class RenderFooterTests(TestCase):
    def test_last_updated_line_present_when_enabled(self):
        cv = CurriculumVitae.objects.create(profile=make_profile())
        block = CVBlock.objects.create(
            cv=cv, kind=CVBlock.KIND_FOOTER, show_last_updated=True
        )
        now = timezone.now()
        html = render_footer(block, now)
        self.assertIn("Last updated", html)
        self.assertIn(str(now.year), html)

    def test_last_updated_line_absent_when_disabled(self):
        cv = CurriculumVitae.objects.create(profile=make_profile())
        block = CVBlock.objects.create(
            cv=cv, kind=CVBlock.KIND_FOOTER, show_last_updated=False,
            content="<p>Referees on request.</p>",
        )
        html = render_footer(block, timezone.now())
        self.assertNotIn("Last updated", html)
        self.assertIn("Referees on request.", html)


class RenderDocumentTests(TestCase):
    def test_document_contains_blocks_in_order_and_pagedjs_scaffold(self):
        profile = make_profile()
        CVWorksStore.objects.create(
            profile=profile,
            records=[{
                "type": "book", "title": "A Book", "date": "2020",
                "refereed": "TRUE", "uri": "https://example.org/1",
                "creators": [{"name": {"given": "A", "family": "B"}}],
            }],
        )
        cv = CurriculumVitae.objects.create(profile=profile)
        CVBlock.objects.create(cv=cv, kind=CVBlock.KIND_HEADER, position=1)
        CVBlock.objects.create(
            cv=cv, kind=CVBlock.KIND_RICHTEXT, position=2,
            heading="Appointments", content="<p>Lecturer</p>",
        )
        CVBlock.objects.create(
            cv=cv, kind=CVBlock.KIND_PUBLICATIONS, position=3,
            works_type="unedited_books",
        )
        html = render_document(cv)
        self.assertIn("Test User", html)
        self.assertIn("Appointments", html)
        self.assertIn("BOOKS (1)", html)
        self.assertIn("A Book", html)
        self.assertIn("__pagedDone", html)
        self.assertIn("static/pagedjs.js", html)
        self.assertLess(html.index("Test User"), html.index("Appointments"))
        self.assertLess(html.index("Appointments"), html.index("BOOKS (1)"))

    def test_publications_block_with_no_store_renders_empty(self):
        cv = CurriculumVitae.objects.create(profile=make_profile())
        CVBlock.objects.create(
            cv=cv, kind=CVBlock.KIND_PUBLICATIONS, position=1,
            works_type="unedited_books",
        )
        html = render_document(cv)
        self.assertNotIn("BOOKS", html)
```

- [ ] **Step 3: Create stub and run tests to verify they fail**

`pipeline/document.py` stub:

```python
def render_header(identity, profile):
    raise NotImplementedError


def render_richtext(block):
    raise NotImplementedError


def render_footer(block, generated_at):
    raise NotImplementedError


def render_document(cv):
    raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement**

`pipeline/document.py`:

```python
"""Render a CurriculumVitae's blocks into the printable HTML document."""

from html import escape

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format

from knowledge_commons_profiles.cv_generator.models import CVBlock
from knowledge_commons_profiles.cv_generator.pipeline.citeproc_engine import (
    CitationRenderer,
)
from knowledge_commons_profiles.cv_generator.pipeline.classify import (
    DEFAULT_HEADINGS,
    classify,
)
from knowledge_commons_profiles.cv_generator.pipeline.csl import RenderOptions
from knowledge_commons_profiles.cv_generator.pipeline.identity import (
    resolve_identity,
)
from knowledge_commons_profiles.cv_generator.pipeline.sections import (
    render_publications_section,
)
from knowledge_commons_profiles.newprofile.utils import sanitize_html

import logging

logger = logging.getLogger(__name__)


def render_header(identity, profile):
    """The PersonInfo-style header block, auto-filled from the profile."""
    lines = [
        f'<h1 id="person" class="personinfo">{escape(identity.name)}</h1>',
        '<p id="cv" class="personinfo"><small><i>Curriculum Vitae</i>'
        "</small></p>",
    ]

    for value in (profile.title, profile.affiliation):
        if value:
            lines.append(f'<p class="personinfo">{escape(value)}</p>')

    lines.append('<p class="personinfo" aria-hidden="true">&nbsp;</p>')

    for email in identity.emails:
        email = escape(email)
        lines.append(
            f'<p class="personinfo">email: '
            f'<a href="mailto:{email}">{email}</a></p>'
        )

    if identity.orcid:
        orcid = escape(identity.orcid)
        lines.append(
            f'<p class="personinfo">ORCID: '
            f'<a href="https://orcid.org/{orcid}">{orcid}</a></p>'
        )

    return '<div id="personinfo">' + "".join(lines) + "</div>"


def _wrapped_section(block, inner):
    heading_html = ""
    labelled = ""
    if block.heading:
        heading_id = f"block-{block.pk}-heading"
        heading_html = (
            f'<h2 id="{heading_id}" class="sectionheader">'
            f"{escape(block.heading)}</h2>"
        )
        labelled = f' aria-labelledby="{heading_id}"'
    return (
        f'<section class="section"{labelled}>{heading_html}{inner}</section>'
    )


def render_richtext(block):
    """A user-written section: sanitized HTML under an optional heading."""
    content = sanitize_html(block.content) if block.content else ""
    if not content and not block.heading:
        return ""
    return _wrapped_section(block, f'<div class="richtext">{content}</div>')


def render_footer(block, generated_at):
    """End matter: sanitized rich text plus an optional last-updated line."""
    content = sanitize_html(block.content) if block.content else ""
    if block.show_last_updated:
        stamp = date_format(generated_at, "j F Y")
        content += f'<p class="cv-last-updated">Last updated {stamp}</p>'
    if not content and not block.heading:
        return ""
    return _wrapped_section(block, f'<div class="richtext">{content}</div>')


def render_document(cv):
    """
    Render the whole CV to the printable Paged.js HTML document.
    :param cv: a CurriculumVitae
    :return: a complete HTML document string
    """
    profile = cv.profile
    identity = resolve_identity(profile)

    store = getattr(profile, "cv_works_store", None)
    options = RenderOptions.from_cv(cv)
    classified = (
        classify(store.records, options.review_of)
        if store and store.records
        else {}
    )
    renderer = CitationRenderer(logger, locale=options.citation_locale)

    now = timezone.now()
    parts = []
    for block in cv.blocks.all():
        if block.kind == CVBlock.KIND_HEADER:
            parts.append(render_header(identity, profile))
        elif block.kind == CVBlock.KIND_RICHTEXT:
            parts.append(render_richtext(block))
        elif block.kind == CVBlock.KIND_FOOTER:
            parts.append(render_footer(block, now))
        elif block.kind == CVBlock.KIND_PUBLICATIONS:
            items = classified.get(block.works_type, [])
            heading = block.heading or DEFAULT_HEADINGS.get(
                block.works_type, block.works_type
            )
            parts.append(
                render_publications_section(
                    items, block.works_type, heading, options, renderer
                )
            )

    return render_to_string(
        "cv_generator/pdf_document.html",
        {"title": identity.name, "body": "".join(part for part in parts if part)},
    )
```

`templates/cv_generator/pdf_document.html` — modelled on `$EPRINTSTOCV/templates/PDF` (no Typekit; assets served relatively by the print server; `{{ body }}` replaces the hardcoded section placeholders):

```html
<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <title>{{ title }}: Curriculum Vitae</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description"
        content="The academic curriculum vitae of {{ title }}">
  <link rel="stylesheet" href="static/pagedjs.css">
  <link rel="stylesheet" href="static/cv.css">
  <script>
    /* signal to the printing process when Paged.js has finished laying
       out the document; before signalling, write the "page/total" folio
       into each page's top-right margin box (this build of Paged.js
       predates counter(pages)). */
    window.__pagedDone = false;
    window.onPagesRendered = function () {
      var pages = document.querySelectorAll('.pagedjs_page');
      pages.forEach(function (page, index) {
        if (page.classList.contains('pagedjs_blank_page')) { return; }
        var box = page.querySelector('.pagedjs_margin-top-right');
        if (!box) { return; }
        box.classList.add('hasContent');
        box.querySelector('.pagedjs_margin-content').textContent =
          (index + 1) + '/' + pages.length;
      });
      window.__pagedDone = true;
    };
  </script>
  <script src="static/pagedjs.js"></script>
</head>
<body>
<main id="cassius-content">
<div class="main">
{{ body }}
</div>
</main>
<article id="article"></article>
</body>
</html>
```

Template-safety note: `{{ body }}` is model-derived HTML — mark it safe in the view context instead of using `|safe` scattered: pass `mark_safe(body)` (`from django.utils.safestring import mark_safe`) in `render_document`'s context dict: `{"title": identity.name, "body": mark_safe(...)}`. Every constituent is either escaped here or sanitized by `sanitize_html`.

Check `$EPRINTSTOCV/templates/PDF` for whether the reference template inlines the `onPagesRendered` hook differently (e.g. `window.PagedConfig`); copy the working mechanism from that file verbatim if it differs from the above.

- [ ] **Step 5: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): render CV blocks into the printable Paged.js document"
```

---

### Task 12: PDF printing with Playwright

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/pipeline/printpdf.py` (copied + adapted)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_pipeline_printpdf.py`
- Modify: `pyproject.toml` (add `playwright`)
- Modify: `config/settings/base.py` (add `CV_RENDER_CONCURRENCY` and `CV_RENDER_TIMEOUT_MS`)

**Interfaces:**
- Consumes: the vendored `static/cv_generator/pagedjs/` assets (Task 11).
- Produces: `printpdf.print_html_to_pdf(html: str, output_path) -> Path` — writes the HTML plus the pagedjs assets into a temp dir, serves it loopback-only, waits for `window.__pagedDone`, and writes a tagged, outlined PDF to `output_path`. Concurrency is capped by a module `threading.BoundedSemaphore(settings.CV_RENDER_CONCURRENCY)`; the Paged.js wait uses `settings.CV_RENDER_TIMEOUT_MS`. Also `printpdf.serve_directory(root)` (the ported loopback server, renamed from `serve_project`).

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_pipeline_printpdf.py`:

```python
"""PDF printing: asset staging and Playwright orchestration (mocked)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from knowledge_commons_profiles.cv_generator.pipeline import printpdf


class PrintHtmlToPdfTests(SimpleTestCase):
    @mock.patch(
        "knowledge_commons_profiles.cv_generator.pipeline.printpdf"
        ".sync_playwright"
    )
    def test_stages_assets_and_prints_tagged_pdf(self, sync_playwright):
        playwright = sync_playwright.return_value.__enter__.return_value
        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value

        staged = {}

        def capture_goto(url, **kwargs):
            # the served directory must contain index.html and the assets
            root = printpdf._LAST_SERVED_ROOT
            staged["files"] = sorted(
                str(p.relative_to(root)) for p in Path(root).rglob("*")
                if p.is_file()
            )

        page.goto.side_effect = capture_goto

        with tempfile.TemporaryDirectory() as out_dir:
            out = Path(out_dir) / "cv.pdf"
            result = printpdf.print_html_to_pdf("<html>x</html>", out)

        self.assertEqual(result, out)
        self.assertIn("index.html", staged["files"])
        self.assertIn("static/pagedjs.js", staged["files"])
        self.assertIn("static/pagedjs.css", staged["files"])
        self.assertIn("static/cv.css", staged["files"])

        page.wait_for_function.assert_called_once()
        self.assertIn(
            "__pagedDone", page.wait_for_function.call_args.args[0]
        )
        pdf_kwargs = page.pdf.call_args.kwargs
        self.assertEqual(pdf_kwargs["path"], str(out))
        self.assertTrue(pdf_kwargs["tagged"])
        self.assertTrue(pdf_kwargs["outline"])

    @mock.patch(
        "knowledge_commons_profiles.cv_generator.pipeline.printpdf"
        ".sync_playwright"
    )
    def test_browser_closed_even_when_print_fails(self, sync_playwright):
        playwright = sync_playwright.return_value.__enter__.return_value
        browser = playwright.chromium.launch.return_value
        browser.new_page.return_value.pdf.side_effect = RuntimeError("boom")

        with tempfile.TemporaryDirectory() as out_dir:
            with self.assertRaises(RuntimeError):
                printpdf.print_html_to_pdf(
                    "<html>x</html>", Path(out_dir) / "cv.pdf"
                )

        browser.close.assert_called_once()
```

(The `_LAST_SERVED_ROOT` module attribute is part of the implementation contract below — it exists precisely so tests can observe the staged directory without reaching into threading internals.)

- [ ] **Step 2: Create stub and run tests to verify they fail**

`pipeline/printpdf.py` stub:

```python
from playwright.sync_api import sync_playwright  # noqa: F401

_LAST_SERVED_ROOT = None


def serve_directory(root):
    raise NotImplementedError


def print_html_to_pdf(html, output_path):
    raise NotImplementedError
```

First `uv add playwright`, then run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

Start from `$EPRINTSTOCV/cv/printpdf.py` (`_ProjectRequestHandler`, `serve_project` → `serve_directory`, MIME map, `BROWSER_ARGS` — copy those parts verbatim), then replace `print_pdf` with:

```python
import shutil
import tempfile
import threading
from pathlib import Path

from django.conf import settings

ASSETS_DIR = (
    Path(__file__).resolve().parents[1]
    / "static" / "cv_generator" / "pagedjs"
)

_render_slots = threading.BoundedSemaphore(
    getattr(settings, "CV_RENDER_CONCURRENCY", 2)
)

# observability hook for tests: the directory most recently served
_LAST_SERVED_ROOT = None


def print_html_to_pdf(html, output_path):
    """
    Print an HTML document (as produced by document.render_document) to
    a tagged, accessible PDF.
    :param html: the complete HTML document string
    :param output_path: where to write the PDF
    :return: output_path as a Path
    """
    global _LAST_SERVED_ROOT
    output_path = Path(output_path)
    timeout_ms = getattr(settings, "CV_RENDER_TIMEOUT_MS", 120000)

    with _render_slots, tempfile.TemporaryDirectory() as workdir:
        workdir = Path(workdir)
        static_dir = workdir / "static"
        static_dir.mkdir()
        for asset in ASSETS_DIR.iterdir():
            shutil.copy(asset, static_dir / asset.name)
        (workdir / "index.html").write_text(html, encoding="utf-8")

        _LAST_SERVED_ROOT = str(workdir)
        server = serve_directory(workdir)
        port = server.server_address[1]

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True, args=BROWSER_ARGS
                )
                try:
                    page = browser.new_page()
                    page.goto(
                        f"http://127.0.0.1:{port}/index.html",
                        wait_until="networkidle",
                        timeout=60000,
                    )
                    page.wait_for_function(
                        "window.__pagedDone === true", timeout=timeout_ms
                    )
                    page.pdf(
                        path=str(output_path),
                        tagged=True,
                        outline=True,
                        prefer_css_page_size=True,
                        print_background=True,
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()

    return output_path
```

In `config/settings/base.py`, near the other feature settings:

```python
# CV generator: concurrent headless-Chromium renders and the Paged.js
# layout timeout
CV_RENDER_CONCURRENCY = env.int("CV_RENDER_CONCURRENCY", default=2)
CV_RENDER_TIMEOUT_MS = env.int("CV_RENDER_TIMEOUT_MS", default=120000)
```

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS (Playwright fully mocked; no browser needed).

- [ ] **Step 5: Optional integration check, then commit**

If Chromium is installed locally (`uv run playwright install chromium` to get it), add this manually-run smoke check and confirm it passes once, but decorate it so CI never needs a browser:

```python
@unittest.skipUnless(
    os.environ.get("CV_PDF_INTEGRATION") == "1",
    "set CV_PDF_INTEGRATION=1 and install Chromium to run",
)
class RealChromiumTests(SimpleTestCase):
    def test_end_to_end_pdf_bytes(self):
        html = (
            "<html><head><script>window.__pagedDone = true;</script>"
            "</head><body><h1>CV</h1></body></html>"
        )
        with tempfile.TemporaryDirectory() as out_dir:
            out = printpdf.print_html_to_pdf(html, Path(out_dir) / "c.pdf")
            self.assertTrue(out.read_bytes().startswith(b"%PDF"))
```

```bash
git add knowledge_commons_profiles/cv_generator config/settings/base.py pyproject.toml uv.lock
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): print CVs to tagged PDFs via Paged.js and headless Chromium"
```

---

### Task 13: Setup service — first-visit defaults

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/services.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_services_setup.py`
- Modify: `config/settings/base.py` (add `CV_KC_WORKS_API`)

**Interfaces:**
- Consumes: models (Task 2), `fetch.DEFAULT_INVENIO_SEARCH` (Task 8).
- Produces:
  - Setting `CV_KC_WORKS_API` (env-overridable, default `"https://works.hcommons.org/api/records"`).
  - `services.DEFAULT_BLOCKS` — the spec's default layout (list of kwargs dicts, in order): header; richtext "Appointments"; richtext "Education"; publications `unedited_books`; publications `edited_books`; publications `peer_reviewed_articles`; footer.
  - `services.ensure_cv_setup(profile) -> CurriculumVitae` — idempotent: creates (once each) the profile's `CVWorksStore`, the KC Works `CVRepository` (only when the profile has NO repositories at all — a user who deleted KC Works must not have it resurrected), and, when the profile has no CVs, a first CV named "My CV", `is_active=True`, `citation_style` seeded from `profile.reference_style` (falling back to "MHRA" when blank/unknown), carrying `DEFAULT_BLOCKS`. Returns the profile's active CV (or first CV if none active).
  - `services.create_cv(profile, name) -> CurriculumVitae` — a new CV with the default block layout, active only if the profile has no active CV.
  - `services.duplicate_cv(cv, name) -> CurriculumVitae` — copies options and blocks; never active.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_services_setup.py`:

```python
"""First-visit defaults: works store, KC Works repository, default CV."""

from django.test import TestCase, override_settings

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVRepository,
    CurriculumVitae,
)
from knowledge_commons_profiles.newprofile.models import Profile


def make_profile(**kwargs):
    defaults = {"name": "Test User", "username": "kcuser"}
    defaults.update(kwargs)
    return Profile.objects.create(**defaults)


@override_settings(CV_KC_WORKS_API="https://works.example.org/api/records")
class EnsureCvSetupTests(TestCase):
    def test_creates_store_kc_repo_and_default_cv(self):
        profile = make_profile()
        cv = services.ensure_cv_setup(profile)

        repo = profile.cv_repositories.get()
        self.assertEqual(repo.kind, CVRepository.KIND_INVENIO)
        self.assertEqual(repo.endpoint,
                         "https://works.example.org/api/records")
        self.assertEqual(repo.label, "KC Works")
        self.assertEqual(
            repo.search_config,
            {"strategies": ["username", "orcid", "name"], "mode": "union"},
        )

        self.assertTrue(hasattr(profile, "cv_works_store"))
        self.assertTrue(cv.is_active)
        kinds = [(b.kind, b.heading, b.works_type)
                 for b in cv.blocks.all()]
        self.assertEqual(kinds, [
            ("header", "", ""),
            ("richtext", "Appointments", ""),
            ("richtext", "Education", ""),
            ("publications", "", "unedited_books"),
            ("publications", "", "edited_books"),
            ("publications", "", "peer_reviewed_articles"),
            ("footer", "", ""),
        ])

    def test_idempotent_on_second_call(self):
        profile = make_profile()
        first = services.ensure_cv_setup(profile)
        second = services.ensure_cv_setup(profile)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(profile.cv_repositories.count(), 1)
        self.assertEqual(profile.cvs.count(), 1)

    def test_deleted_kc_works_is_not_resurrected(self):
        profile = make_profile()
        services.ensure_cv_setup(profile)
        profile.cv_repositories.all().delete()
        CVRepository.objects.create(
            profile=profile, kind=CVRepository.KIND_EPRINTS,
            endpoint="eprints.example.org",
        )
        services.ensure_cv_setup(profile)
        self.assertEqual(profile.cv_repositories.count(), 1)
        self.assertEqual(profile.cv_repositories.get().kind,
                         CVRepository.KIND_EPRINTS)

    def test_citation_style_seeded_from_profile_reference_style(self):
        profile = make_profile(reference_style="APA", username="apa")
        cv = services.ensure_cv_setup(profile)
        self.assertEqual(cv.citation_style, "APA")

    def test_unknown_reference_style_falls_back_to_mhra(self):
        profile = make_profile(reference_style=None, username="none")
        cv = services.ensure_cv_setup(profile)
        self.assertEqual(cv.citation_style, "MHRA")


class CreateAndDuplicateTests(TestCase):
    def test_create_cv_gets_default_blocks_and_activity(self):
        profile = make_profile()
        first = services.create_cv(profile, "Full CV")
        self.assertTrue(first.is_active)
        second = services.create_cv(profile, "Short CV")
        self.assertFalse(second.is_active)
        self.assertEqual(second.blocks.count(), len(services.DEFAULT_BLOCKS))

    def test_duplicate_copies_blocks_and_options_but_not_activity(self):
        profile = make_profile()
        original = services.create_cv(profile, "Full CV")
        original.citation_link = CurriculumVitae.LINK_ENTRY
        original.save()
        block = original.blocks.filter(kind=CVBlock.KIND_RICHTEXT).first()
        block.content = "<p>Hi</p>"
        block.save()

        copy = services.duplicate_cv(original, "Copy of Full CV")
        self.assertFalse(copy.is_active)
        self.assertEqual(copy.citation_link, CurriculumVitae.LINK_ENTRY)
        self.assertEqual(copy.blocks.count(), original.blocks.count())
        copied_block = copy.blocks.filter(kind=CVBlock.KIND_RICHTEXT).first()
        self.assertEqual(copied_block.content, "<p>Hi</p>")
        self.assertNotEqual(copied_block.pk, block.pk)
```

- [ ] **Step 2: Create stub and run tests to verify they fail**

`services.py` stub:

```python
DEFAULT_BLOCKS = []


def ensure_cv_setup(profile):
    raise NotImplementedError


def create_cv(profile, name):
    raise NotImplementedError


def duplicate_cv(cv, name):
    raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

Add to `config/settings/base.py` next to the Task 12 settings:

```python
CV_KC_WORKS_API = env(
    "CV_KC_WORKS_API", default="https://works.hcommons.org/api/records"
)
```

`services.py`:

```python
"""Orchestration for the CV generator: defaults, refresh, generation."""

import copy
import logging

from django.conf import settings
from django.db import transaction

from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVRepository,
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.cv_generator.pipeline.fetch import (
    DEFAULT_INVENIO_SEARCH,
)
from knowledge_commons_profiles.newprofile.models import CITATION_STYLE_CHOICES

logger = logging.getLogger(__name__)

DEFAULT_BLOCKS = [
    {"kind": CVBlock.KIND_HEADER},
    {"kind": CVBlock.KIND_RICHTEXT, "heading": "Appointments"},
    {"kind": CVBlock.KIND_RICHTEXT, "heading": "Education"},
    {"kind": CVBlock.KIND_PUBLICATIONS, "works_type": "unedited_books"},
    {"kind": CVBlock.KIND_PUBLICATIONS, "works_type": "edited_books"},
    {"kind": CVBlock.KIND_PUBLICATIONS,
     "works_type": "peer_reviewed_articles"},
    {"kind": CVBlock.KIND_FOOTER},
]

_VALID_STYLES = {key for key, _ in CITATION_STYLE_CHOICES}


def _default_style(profile):
    style = profile.reference_style
    return style if style in _VALID_STYLES else "MHRA"


def _add_default_blocks(cv):
    for position, spec in enumerate(DEFAULT_BLOCKS, start=1):
        CVBlock.objects.create(cv=cv, position=position, **spec)


@transaction.atomic
def ensure_cv_setup(profile):
    """
    Create the per-user CV scaffolding on first visit: works store, the
    default KC Works repository (only when the user has never configured
    any repository), and a first, active CV with the default layout.
    Idempotent.
    :param profile: a newprofile.Profile
    :return: the profile's active CV (first CV when none is active)
    """
    CVWorksStore.objects.get_or_create(profile=profile)

    if not profile.cv_repositories.exists():
        CVRepository.objects.create(
            profile=profile,
            kind=CVRepository.KIND_INVENIO,
            endpoint=settings.CV_KC_WORKS_API,
            label="KC Works",
            position=1,
            search_config=dict(DEFAULT_INVENIO_SEARCH),
        )

    if not profile.cvs.exists():
        return create_cv(profile, "My CV")

    active = profile.cvs.filter(is_active=True).first()
    return active or profile.cvs.first()


@transaction.atomic
def create_cv(profile, name):
    """A new CV with the default layout; active if none is yet active."""
    cv = CurriculumVitae.objects.create(
        profile=profile,
        name=name,
        is_active=not profile.cvs.filter(is_active=True).exists(),
        citation_style=_default_style(profile),
    )
    _add_default_blocks(cv)
    return cv


@transaction.atomic
def duplicate_cv(cv, name):
    """A copy of a CV's options and blocks; never active."""
    duplicate = CurriculumVitae.objects.create(
        profile=cv.profile,
        name=name,
        is_active=False,
        citation_style=cv.citation_style,
        citation_locale=cv.citation_locale,
        citation_link=cv.citation_link,
        gold_oa_direct_link=cv.gold_oa_direct_link,
        review_of=cv.review_of,
        titles_to_italicize=cv.titles_to_italicize,
        exclude_venues=copy.deepcopy(cv.exclude_venues),
    )
    for block in cv.blocks.all():
        CVBlock.objects.create(
            cv=duplicate,
            position=block.position,
            kind=block.kind,
            heading=block.heading,
            content=block.content,
            works_type=block.works_type,
            show_last_updated=block.show_last_updated,
        )
    return duplicate
```

Note the empty-string expectations in the tests (`heading`, `works_type` default to `""` via the model's `blank=True` CharFields) — `DEFAULT_BLOCKS` relies on those defaults.

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator config/settings/base.py
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): create default repositories, store and CV layout on first visit"
```

---

### Task 14: Refresh and generation services (threads + state machines)

**Files:**
- Modify: `knowledge_commons_profiles/cv_generator/services.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_services_jobs.py`

**Interfaces:**
- Consumes: `fetch.fetch_works`/`FetchFailed` (Task 8), `document.render_document` (Task 11), `printpdf.print_html_to_pdf` (Task 12), models.
- Produces:
  - `services.start_refresh(profile) -> bool` — False (no-op) when a fetch is already in flight and not stalled; otherwise flips the store to `fetching` (updating `status_changed_at`), spawns `_run_refresh` on a daemon thread, returns True.
  - `services._run_refresh(profile_id)` — thread body: on success stores records + provenance + `fetched_at`, status `idle`; on `FetchFailed` sets status `error` + `error_detail`, PRESERVING previous records; any unexpected exception also lands in `error` (never left stuck in `fetching`).
  - `services.start_generation(cv) -> bool` — same in-flight/stalled guard on the CV; spawns `_run_generation`.
  - `services._run_generation(cv_id)` — renders HTML, prints the PDF to a temp file, saves bytes to `cv.generated_file` (UUID name via `generated_pdf_path`), sets `generated_at`, status `idle`; when `cv.is_active`, also writes the same bytes to `profile.cv_file` (named `generated-cv.pdf`; `cv_file_path` UUIDs it). Errors → status `error` + `error_detail`, previous files untouched.
  - `services.start_update_active(profile) -> bool` — one thread that refreshes and then (if refresh succeeded) generates the active CV; guards as above; False when the profile has no active CV.
  - `services._spawn(target, *args)` — the single place threads are created (`threading.Thread(..., daemon=True).start()`); tests monkeypatch it to run inline. Every thread body must call `django.db.close_old_connections()` at start and end, and wrap everything in try/except.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_services_jobs.py`:

```python
"""Refresh and generation job orchestration (threads run inline)."""

from datetime import timedelta
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.cv_generator.pipeline.fetch import FetchFailed
from knowledge_commons_profiles.newprofile.models import Profile


def run_inline(target, *args):
    target(*args)


def make_profile(username="kcuser"):
    return Profile.objects.create(name="Test User", username=username)


@mock.patch.object(services, "_spawn", side_effect=run_inline)
class RefreshTests(TestCase):
    def setUp(self):
        self.profile = make_profile()
        self.store = CVWorksStore.objects.create(profile=self.profile)

    def test_successful_refresh_stores_records_and_provenance(self, _spawn):
        with mock.patch.object(
            services, "fetch_works",
            return_value=([{"title": "A"}], "the provenance"),
        ):
            self.assertTrue(services.start_refresh(self.profile))

        self.store.refresh_from_db()
        self.assertEqual(self.store.status, CVWorksStore.STATUS_IDLE)
        self.assertEqual(self.store.records, [{"title": "A"}])
        self.assertEqual(self.store.provenance, "the provenance")
        self.assertIsNotNone(self.store.fetched_at)

    def test_failed_refresh_preserves_previous_records(self, _spawn):
        self.store.records = [{"title": "Old"}]
        self.store.save()
        with mock.patch.object(
            services, "fetch_works",
            side_effect=FetchFailed([("KC Works", "boom")]),
        ):
            services.start_refresh(self.profile)

        self.store.refresh_from_db()
        self.assertEqual(self.store.status, CVWorksStore.STATUS_ERROR)
        self.assertEqual(self.store.records, [{"title": "Old"}])
        self.assertIn("KC Works", self.store.error_detail)

    def test_unexpected_exception_lands_in_error_not_stuck(self, _spawn):
        with mock.patch.object(
            services, "fetch_works", side_effect=ValueError("bug"),
        ):
            services.start_refresh(self.profile)
        self.store.refresh_from_db()
        self.assertEqual(self.store.status, CVWorksStore.STATUS_ERROR)

    def test_in_flight_refresh_is_not_restarted(self, _spawn):
        self.store.status = CVWorksStore.STATUS_FETCHING
        self.store.status_changed_at = timezone.now()
        self.store.save()
        self.assertFalse(services.start_refresh(self.profile))

    def test_stalled_refresh_can_be_restarted(self, _spawn):
        self.store.status = CVWorksStore.STATUS_FETCHING
        self.store.status_changed_at = timezone.now() - timedelta(minutes=11)
        self.store.save()
        with mock.patch.object(
            services, "fetch_works", return_value=([], "p"),
        ):
            self.assertTrue(services.start_refresh(self.profile))


@mock.patch.object(services, "_spawn", side_effect=run_inline)
class GenerationTests(TestCase):
    def setUp(self):
        self.profile = make_profile()
        self.cv = CurriculumVitae.objects.create(
            profile=self.profile, is_active=True
        )

    def _patch_pipeline(self):
        render = mock.patch.object(
            services, "render_document", return_value="<html>cv</html>"
        )

        def fake_print(html, output_path):
            from pathlib import Path

            Path(output_path).write_bytes(b"%PDF-fake")
            return Path(output_path)

        printer = mock.patch.object(
            services, "print_html_to_pdf", side_effect=fake_print
        )
        return render, printer

    def test_generation_saves_uuid_file_and_updates_profile(self, _spawn):
        render, printer = self._patch_pipeline()
        with render, printer:
            self.assertTrue(services.start_generation(self.cv))

        self.cv.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.cv.generation_status,
                         CurriculumVitae.STATUS_IDLE)
        self.assertRegex(self.cv.generated_file.name,
                         r"^cv_generator/[0-9a-f]{32}\.pdf$")
        self.assertRegex(self.profile.cv_file.name,
                         r"^cvs/[0-9a-f]{32}\.pdf$")
        self.assertEqual(self.profile.cv_file.read(), b"%PDF-fake")

    def test_inactive_cv_does_not_touch_profile_file(self, _spawn):
        self.cv.is_active = False
        self.cv.save()
        render, printer = self._patch_pipeline()
        with render, printer:
            services.start_generation(self.cv)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.cv_file)

    def test_failed_generation_preserves_previous_pdf(self, _spawn):
        self.cv.generated_file.save("x.pdf", ContentFile(b"%PDF-old"))
        old_name = self.cv.generated_file.name
        render, _ = self._patch_pipeline()
        with render, mock.patch.object(
            services, "print_html_to_pdf",
            side_effect=RuntimeError("chromium died"),
        ):
            services.start_generation(self.cv)

        self.cv.refresh_from_db()
        self.assertEqual(self.cv.generation_status,
                         CurriculumVitae.STATUS_ERROR)
        self.assertEqual(self.cv.generated_file.name, old_name)
        self.assertIn("chromium died", self.cv.error_detail)

    def test_in_flight_generation_is_not_restarted(self, _spawn):
        self.cv.generation_status = CurriculumVitae.STATUS_GENERATING
        self.cv.generation_started_at = timezone.now()
        self.cv.save()
        self.assertFalse(services.start_generation(self.cv))


@mock.patch.object(services, "_spawn", side_effect=run_inline)
class UpdateActiveTests(TestCase):
    def test_refresh_then_generate_in_one_job(self, _spawn):
        profile = make_profile()
        CVWorksStore.objects.create(profile=profile)
        cv = CurriculumVitae.objects.create(profile=profile, is_active=True)

        def fake_print(html, output_path):
            from pathlib import Path

            Path(output_path).write_bytes(b"%PDF-fake")
            return Path(output_path)

        with mock.patch.object(
            services, "fetch_works", return_value=([{"title": "A"}], "p"),
        ), mock.patch.object(
            services, "render_document", return_value="<html></html>"
        ), mock.patch.object(
            services, "print_html_to_pdf", side_effect=fake_print
        ):
            self.assertTrue(services.start_update_active(profile))

        cv.refresh_from_db()
        self.assertEqual(cv.generation_status, CurriculumVitae.STATUS_IDLE)
        profile.refresh_from_db()
        self.assertTrue(profile.cv_file)

    def test_no_active_cv_returns_false(self, _spawn):
        profile = make_profile()
        CVWorksStore.objects.create(profile=profile)
        self.assertFalse(services.start_update_active(profile))

    def test_failed_refresh_skips_generation(self, _spawn):
        profile = make_profile()
        store = CVWorksStore.objects.create(profile=profile)
        cv = CurriculumVitae.objects.create(profile=profile, is_active=True)
        with mock.patch.object(
            services, "fetch_works",
            side_effect=FetchFailed([("KC Works", "down")]),
        ), mock.patch.object(services, "render_document") as render:
            services.start_update_active(profile)
        cv.refresh_from_db()
        self.assertEqual(cv.generation_status, CurriculumVitae.STATUS_IDLE)
        render.assert_not_called()
        store.refresh_from_db()
        self.assertEqual(store.status, CVWorksStore.STATUS_ERROR)
```

- [ ] **Step 2: Add stubs and run tests to verify they fail**

Append to `services.py`:

```python
def _spawn(target, *args):
    raise NotImplementedError


def start_refresh(profile):
    raise NotImplementedError


def _run_refresh(profile_id):
    raise NotImplementedError


def start_generation(cv):
    raise NotImplementedError


def _run_generation(cv_id):
    raise NotImplementedError


def start_update_active(profile):
    raise NotImplementedError
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace the stubs in `services.py` (new imports at top: `import tempfile`, `import threading`, `from pathlib import Path`, `from django.core.files.base import ContentFile`, `from django.db import close_old_connections`, `from django.utils import timezone`, `from knowledge_commons_profiles.cv_generator.pipeline.document import render_document`, `from knowledge_commons_profiles.cv_generator.pipeline.fetch import FetchFailed, fetch_works`, `from knowledge_commons_profiles.cv_generator.pipeline.printpdf import print_html_to_pdf`, `from knowledge_commons_profiles.newprofile.models import Profile`):

```python
def _spawn(target, *args):
    """Run a job on a daemon thread (patched to run inline in tests)."""
    threading.Thread(target=target, args=args, daemon=True).start()


def start_refresh(profile):
    """
    Kick off a background works refresh unless one is already running.
    :param profile: a newprofile.Profile
    :return: True when a job was started
    """
    store, _ = CVWorksStore.objects.get_or_create(profile=profile)

    if store.status == CVWorksStore.STATUS_FETCHING and (
        not store.fetch_is_stalled()
    ):
        return False

    store.status = CVWorksStore.STATUS_FETCHING
    store.status_changed_at = timezone.now()
    store.error_detail = ""
    store.save(
        update_fields=["status", "status_changed_at", "error_detail"]
    )

    _spawn(_run_refresh, profile.pk)
    return True


def _refresh_inner(profile):
    store = profile.cv_works_store
    try:
        records, provenance = fetch_works(profile)
    except FetchFailed as failure:
        store.status = CVWorksStore.STATUS_ERROR
        store.error_detail = str(failure)
        store.status_changed_at = timezone.now()
        store.save(
            update_fields=["status", "error_detail", "status_changed_at"]
        )
        return False
    except Exception:
        logger.exception("Unexpected error refreshing works for %s",
                         profile.username)
        store.status = CVWorksStore.STATUS_ERROR
        store.error_detail = "Unexpected error while fetching."
        store.status_changed_at = timezone.now()
        store.save(
            update_fields=["status", "error_detail", "status_changed_at"]
        )
        return False

    store.records = records
    store.provenance = provenance
    store.fetched_at = timezone.now()
    store.status = CVWorksStore.STATUS_IDLE
    store.status_changed_at = timezone.now()
    store.error_detail = ""
    store.save()
    return True


def _run_refresh(profile_id):
    close_old_connections()
    try:
        profile = Profile.objects.get(pk=profile_id)
        _refresh_inner(profile)
    finally:
        close_old_connections()


def start_generation(cv):
    """
    Kick off a background PDF generation unless one is already running.
    :param cv: a CurriculumVitae
    :return: True when a job was started
    """
    if cv.generation_status == CurriculumVitae.STATUS_GENERATING and (
        not cv.generation_is_stalled()
    ):
        return False

    cv.generation_status = CurriculumVitae.STATUS_GENERATING
    cv.generation_started_at = timezone.now()
    cv.error_detail = ""
    cv.save(
        update_fields=[
            "generation_status", "generation_started_at", "error_detail",
        ]
    )

    _spawn(_run_generation, cv.pk)
    return True


def _generate_inner(cv):
    try:
        html = render_document(cv)
        with tempfile.TemporaryDirectory() as workdir:
            pdf_path = Path(workdir) / "cv.pdf"
            print_html_to_pdf(html, pdf_path)
            pdf_bytes = pdf_path.read_bytes()
    except Exception as error:  # noqa: BLE001 - job boundary
        logger.exception("CV generation failed for CV %s", cv.pk)
        cv.generation_status = CurriculumVitae.STATUS_ERROR
        cv.error_detail = str(error) or "Unexpected error while generating."
        cv.save(update_fields=["generation_status", "error_detail"])
        return False

    cv.generated_file.save("cv.pdf", ContentFile(pdf_bytes), save=False)
    cv.generated_at = timezone.now()
    cv.generation_status = CurriculumVitae.STATUS_IDLE
    cv.error_detail = ""
    cv.save()

    if cv.is_active:
        profile = cv.profile
        profile.cv_file.save(
            "generated-cv.pdf", ContentFile(pdf_bytes), save=True
        )

    return True


def _run_generation(cv_id):
    close_old_connections()
    try:
        cv = CurriculumVitae.objects.select_related("profile").get(pk=cv_id)
        _generate_inner(cv)
    finally:
        close_old_connections()


def start_update_active(profile):
    """
    Refresh works then regenerate the active CV, as one background job
    (the edit-page "Update from repositories" link).
    :param profile: a newprofile.Profile
    :return: True when a job was started
    """
    cv = profile.cvs.filter(is_active=True).first()
    if cv is None:
        return False

    store, _ = CVWorksStore.objects.get_or_create(profile=profile)
    if store.status == CVWorksStore.STATUS_FETCHING and (
        not store.fetch_is_stalled()
    ):
        return False
    if cv.generation_status == CurriculumVitae.STATUS_GENERATING and (
        not cv.generation_is_stalled()
    ):
        return False

    store.status = CVWorksStore.STATUS_FETCHING
    store.status_changed_at = timezone.now()
    store.save(update_fields=["status", "status_changed_at"])
    cv.generation_status = CurriculumVitae.STATUS_GENERATING
    cv.generation_started_at = timezone.now()
    cv.save(
        update_fields=["generation_status", "generation_started_at"]
    )

    _spawn(_run_update_active, profile.pk, cv.pk)
    return True


def _run_update_active(profile_id, cv_id):
    close_old_connections()
    try:
        profile = Profile.objects.get(pk=profile_id)
        cv = CurriculumVitae.objects.select_related("profile").get(pk=cv_id)
        if _refresh_inner(profile):
            _generate_inner(cv)
        else:
            cv.generation_status = CurriculumVitae.STATUS_IDLE
            cv.save(update_fields=["generation_status"])
    finally:
        close_old_connections()
```

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS. (These tests exercise real file storage; local settings use filesystem MEDIA_ROOT.)

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add threaded refresh and PDF generation services"
```

---

### Task 15: Forms and repository-endpoint validation (SSRF posture)

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/forms.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_forms.py`

**Interfaces:**
- Consumes: models (Task 2), `CITATION_STYLE_CHOICES`.
- Produces:
  - `forms.validate_repository_endpoint(value: str) -> str` — accepts `http(s)://` URLs and (for eprints) bare hostnames; normalises bare hostnames to `https://<host>`… NO: keep the pipeline contract — eprints endpoints stay bare hostnames (EprintsSource adds the scheme). The validator therefore: rejects non-http(s) schemes, rejects userinfo (`user@host`), rejects hosts that are IP literals in private/loopback/link-local/reserved ranges (use `ipaddress.ip_address`), rejects `localhost` and hostnames without a dot, and returns the value unchanged. Raises `django.core.exceptions.ValidationError` with a user-readable message.
  - `forms.RepositoryForm(ModelForm)` for `CVRepository` fields `kind`, `endpoint`, `label` — endpoint checked by the validator; for `KIND_INVENIO` the endpoint must be a full http(s) URL (it is an API base); for `KIND_EPRINTS` a bare hostname or URL is accepted.
  - `forms.AdvancedOptionsForm(ModelForm)` for `CurriculumVitae` fields `citation_style`, `citation_locale` (choices: `en-GB`, `en-US`), `citation_link`, `gold_oa_direct_link`, `review_of`, `titles_to_italicize` (Textarea).
  - `forms.IdentityForm(ModelForm)` for `CVIdentity` fields `name`, `orcid` plus a `emails` CharField (comma-separated in the UI, cleaned to a list).

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_forms.py`:

```python
"""Form validation, especially the SSRF posture of repository endpoints."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from knowledge_commons_profiles.cv_generator.forms import (
    IdentityForm,
    RepositoryForm,
    validate_repository_endpoint,
)


class EndpointValidatorTests(SimpleTestCase):
    def test_public_https_url_is_accepted(self):
        self.assertEqual(
            validate_repository_endpoint(
                "https://works.hcommons.org/api/records"
            ),
            "https://works.hcommons.org/api/records",
        )

    def test_bare_hostname_is_accepted(self):
        self.assertEqual(
            validate_repository_endpoint("eprints.bbk.ac.uk"),
            "eprints.bbk.ac.uk",
        )

    def test_rejections(self):
        bad = [
            "ftp://example.org/x",          # non-http scheme
            "file:///etc/passwd",           # local file
            "https://user@example.org/",    # userinfo smuggling
            "https://127.0.0.1/api",        # loopback
            "https://10.0.0.5/api",         # private range
            "https://169.254.169.254/meta", # link-local metadata
            "https://[::1]/api",            # IPv6 loopback
            "localhost",                    # loopback by name
            "https://internal/api",         # dotless internal hostname
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_repository_endpoint(value)


class RepositoryFormTests(TestCase):
    def test_invenio_requires_full_url(self):
        form = RepositoryForm(
            data={"kind": "invenio", "endpoint": "works.hcommons.org",
                  "label": "KC Works"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("endpoint", form.errors)

    def test_eprints_accepts_bare_hostname(self):
        form = RepositoryForm(
            data={"kind": "eprints", "endpoint": "eprints.bbk.ac.uk",
                  "label": "Birkbeck"}
        )
        self.assertTrue(form.is_valid(), form.errors)


class IdentityFormTests(TestCase):
    def test_emails_are_split_and_stripped(self):
        form = IdentityForm(
            data={"name": "", "orcid": "",
                  "emails": " a@example.org, b@example.org "}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["emails"],
            ["a@example.org", "b@example.org"],
        )

    def test_invalid_email_rejected(self):
        form = IdentityForm(
            data={"name": "", "orcid": "", "emails": "not-an-email"}
        )
        self.assertFalse(form.is_valid())
```

- [ ] **Step 2: Create stub and run tests to verify they fail**

`forms.py` stub:

```python
from django import forms


def validate_repository_endpoint(value):
    raise NotImplementedError


class RepositoryForm(forms.Form):
    pass


class AdvancedOptionsForm(forms.Form):
    pass


class IdentityForm(forms.Form):
    pass
```

Run the test module. Expected: FAIL (`NotImplementedError` / missing fields).

- [ ] **Step 3: Implement**

`forms.py`:

```python
"""Forms for the CV generator."""

import ipaddress
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from knowledge_commons_profiles.cv_generator.models import (
    CVIdentity,
    CVRepository,
    CurriculumVitae,
)

LOCALE_CHOICES = [("en-GB", "English (UK)"), ("en-US", "English (US)")]


def validate_repository_endpoint(value):
    """
    Validate a repository endpoint for outbound fetching: http(s) only,
    no credentials in the URL, and no loopback/private/link-local hosts,
    so a user cannot point the fetcher at internal infrastructure.
    :param value: a URL or bare hostname
    :return: the value unchanged
    """
    candidate = value if "//" in value else f"//{value}"
    parts = urlsplit(candidate)

    if parts.scheme and parts.scheme not in ("http", "https"):
        raise ValidationError("Only http and https repositories are allowed.")

    if "@" in parts.netloc:
        raise ValidationError("Credentials in repository URLs are not allowed.")

    host = parts.hostname or ""
    if not host:
        raise ValidationError("That does not look like a repository address.")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None and not address.is_global:
        raise ValidationError(
            "Repositories on internal network addresses are not allowed."
        )

    if address is None and ("." not in host or host == "localhost"):
        raise ValidationError(
            "Repository hostnames must be public, fully-qualified names."
        )

    return value


class RepositoryForm(forms.ModelForm):
    class Meta:
        model = CVRepository
        fields = ["kind", "endpoint", "label"]

    def clean_endpoint(self):
        endpoint = self.cleaned_data["endpoint"].strip()
        validate_repository_endpoint(endpoint)

        kind = self.data.get("kind") or self.cleaned_data.get("kind")
        if kind == CVRepository.KIND_INVENIO and not endpoint.startswith(
            ("http://", "https://")
        ):
            raise ValidationError(
                "InvenioRDM repositories need the full API address, "
                "e.g. https://works.hcommons.org/api/records"
            )
        return endpoint


class AdvancedOptionsForm(forms.ModelForm):
    citation_locale = forms.ChoiceField(
        choices=LOCALE_CHOICES, initial="en-GB"
    )

    class Meta:
        model = CurriculumVitae
        fields = [
            "citation_style",
            "citation_locale",
            "citation_link",
            "gold_oa_direct_link",
            "review_of",
            "titles_to_italicize",
        ]
        widgets = {
            "titles_to_italicize": forms.Textarea(attrs={"rows": 6}),
        }


class IdentityForm(forms.ModelForm):
    emails = forms.CharField(
        required=False,
        help_text="Comma-separated list of email addresses.",
    )

    class Meta:
        model = CVIdentity
        fields = ["name", "orcid"]

    def clean_emails(self):
        raw = self.cleaned_data.get("emails", "")
        emails = [e.strip() for e in raw.split(",") if e.strip()]
        for email in emails:
            validate_email(email)
        return emails

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.emails = self.cleaned_data.get("emails", [])
        if commit:
            instance.save()
        return instance
```

(Note: `localhost` reaches the dotless-hostname check, and `169.254.169.254`/`10.x`/`127.x`/`::1` all fail `is_global`.)

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add forms with SSRF-safe repository endpoint validation"
```

---

### Task 16: My CVs list and CV lifecycle views

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/views/helpers.py`
- Create: `knowledge_commons_profiles/cv_generator/views/cvs.py`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/my_cvs.html`
- Modify: `knowledge_commons_profiles/cv_generator/urls.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_cvs.py`

**Interfaces:**
- Consumes: `services.ensure_cv_setup/create_cv/duplicate_cv` (Task 13), models.
- Produces:
  - `helpers.own_profile(request) -> Profile` — the logged-in user's profile via `Profile.objects.get(username=request.user.username)`; raises `Http404` when absent.
  - `helpers.get_own_cv(request, cv_id) -> CurriculumVitae` — 404 unless the CV belongs to the requester (staff may access any, mirroring `newprofile/views/profile/cv.py:22-28`).
  - URL names (namespace `cv_generator`): `my_cvs` (`""`), `create_cv` (`"create/"`, POST), `rename_cv` (`"<int:cv_id>/rename/"`, POST), `duplicate_cv` (`"<int:cv_id>/duplicate/"`, POST), `delete_cv` (`"<int:cv_id>/delete/"`, POST), `activate_cv` (`"<int:cv_id>/activate/"`, POST), `download_cv` (`"<int:cv_id>/download/"`, GET).
  - `my_cvs` GET: runs `ensure_cv_setup`, renders `cv_generator/my_cvs.html` with `cvs`, `profile`.
  - `activate_cv` clears the previous active flag then sets the new one (single transaction). `delete_cv` refuses (redirects with a message) to delete the last remaining CV.
  - `download_cv` returns the generated PDF as `FileResponse` (404 when none).

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_views_cvs.py`:

```python
"""CV list and lifecycle views."""

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cv_generator.models import CurriculumVitae
from knowledge_commons_profiles.newprofile.models import Profile


def make_user_and_profile(username="kcuser"):
    user = get_user_model().objects.create_user(
        username=username, password="pw"
    )
    profile = Profile.objects.create(name="Test User", username=username)
    return user, profile


class MyCvsViewTests(TestCase):
    def setUp(self):
        self.user, self.profile = make_user_and_profile()
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("cv_generator:my_cvs"))
        self.assertEqual(response.status_code, 302)

    def test_first_visit_bootstraps_default_cv(self):
        response = self.client.get(reverse("cv_generator:my_cvs"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.profile.cvs.count(), 1)
        self.assertContains(response, "My CV")

    def test_create_rename_duplicate_activate_delete(self):
        self.client.get(reverse("cv_generator:my_cvs"))
        first = self.profile.cvs.get()

        self.client.post(
            reverse("cv_generator:create_cv"), {"name": "Short CV"}
        )
        short = self.profile.cvs.get(name="Short CV")
        self.assertFalse(short.is_active)

        self.client.post(
            reverse("cv_generator:rename_cv", args=[short.pk]),
            {"name": "Teaching CV"},
        )
        short.refresh_from_db()
        self.assertEqual(short.name, "Teaching CV")

        self.client.post(
            reverse("cv_generator:duplicate_cv", args=[short.pk])
        )
        self.assertEqual(self.profile.cvs.count(), 3)

        self.client.post(
            reverse("cv_generator:activate_cv", args=[short.pk])
        )
        first.refresh_from_db()
        short.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(short.is_active)

        self.client.post(reverse("cv_generator:delete_cv", args=[short.pk]))
        self.assertFalse(
            self.profile.cvs.filter(pk=short.pk).exists()
        )

    def test_last_cv_cannot_be_deleted(self):
        self.client.get(reverse("cv_generator:my_cvs"))
        only = self.profile.cvs.get()
        self.client.post(reverse("cv_generator:delete_cv", args=[only.pk]))
        self.assertTrue(self.profile.cvs.filter(pk=only.pk).exists())

    def test_cannot_touch_another_users_cv(self):
        other_user, other_profile = make_user_and_profile("other")
        cv = CurriculumVitae.objects.create(profile=other_profile)
        response = self.client.post(
            reverse("cv_generator:rename_cv", args=[cv.pk]), {"name": "X"}
        )
        self.assertEqual(response.status_code, 404)

    def test_staff_can_touch_another_users_cv(self):
        self.user.is_staff = True
        self.user.save()
        _other_user, other_profile = make_user_and_profile("other")
        cv = CurriculumVitae.objects.create(profile=other_profile)
        self.client.post(
            reverse("cv_generator:rename_cv", args=[cv.pk]),
            {"name": "Renamed"},
        )
        cv.refresh_from_db()
        self.assertEqual(cv.name, "Renamed")

    def test_download_serves_generated_pdf(self):
        self.client.get(reverse("cv_generator:my_cvs"))
        cv = self.profile.cvs.get()
        cv.generated_file.save("x.pdf", ContentFile(b"%PDF-bytes"))
        response = self.client.get(
            reverse("cv_generator:download_cv", args=[cv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content), b"%PDF-bytes"
        )

    def test_download_without_pdf_is_404(self):
        self.client.get(reverse("cv_generator:my_cvs"))
        cv = self.profile.cvs.get()
        response = self.client.get(
            reverse("cv_generator:download_cv", args=[cv.pk])
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Create stubs and run tests to verify they fail**

`views/helpers.py`:

```python
def own_profile(request):
    raise NotImplementedError


def get_own_cv(request, cv_id):
    raise NotImplementedError
```

`views/cvs.py` — stub each view to `raise NotImplementedError` with the right names (`my_cvs`, `create_cv`, `rename_cv`, `duplicate_cv`, `delete_cv`, `activate_cv`, `download_cv`), and register the URL patterns in `urls.py`:

```python
from django.urls import path

from knowledge_commons_profiles.cv_generator.views import cvs

app_name = "cv_generator"

urlpatterns = [
    path("", cvs.my_cvs, name="my_cvs"),
    path("create/", cvs.create_cv, name="create_cv"),
    path("<int:cv_id>/rename/", cvs.rename_cv, name="rename_cv"),
    path("<int:cv_id>/duplicate/", cvs.duplicate_cv, name="duplicate_cv"),
    path("<int:cv_id>/delete/", cvs.delete_cv, name="delete_cv"),
    path("<int:cv_id>/activate/", cvs.activate_cv, name="activate_cv"),
    path("<int:cv_id>/download/", cvs.download_cv, name="download_cv"),
]
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

`views/helpers.py`:

```python
"""Shared view helpers: ownership scoping for CV objects."""

from django.http import Http404
from django.shortcuts import get_object_or_404

from knowledge_commons_profiles.cv_generator.models import CurriculumVitae
from knowledge_commons_profiles.newprofile.models import Profile


def own_profile(request):
    """The requester's own profile, or 404 when they have none."""
    profile = Profile.objects.filter(
        username=request.user.username
    ).first()
    if profile is None:
        raise Http404
    return profile


def get_own_cv(request, cv_id):
    """A CV the requester may edit: their own, or any for staff."""
    if request.user.is_staff:
        return get_object_or_404(CurriculumVitae, pk=cv_id)
    return get_object_or_404(
        CurriculumVitae, pk=cv_id, profile__username=request.user.username
    )
```

`views/cvs.py`:

```python
"""CV list and lifecycle views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.views.helpers import (
    get_own_cv,
    own_profile,
)


@login_required
def my_cvs(request):
    profile = own_profile(request)
    services.ensure_cv_setup(profile)
    return render(
        request,
        "cv_generator/my_cvs.html",
        {"profile": profile, "cvs": profile.cvs.all()},
    )


@login_required
@require_POST
def create_cv(request):
    profile = own_profile(request)
    name = request.POST.get("name", "").strip() or "My CV"
    cv = services.create_cv(profile, name)
    return redirect("cv_generator:builder", cv_id=cv.pk)


@login_required
@require_POST
def rename_cv(request, cv_id):
    cv = get_own_cv(request, cv_id)
    name = request.POST.get("name", "").strip()
    if name:
        cv.name = name
        cv.save(update_fields=["name"])
    return redirect("cv_generator:my_cvs")


@login_required
@require_POST
def duplicate_cv(request, cv_id):
    cv = get_own_cv(request, cv_id)
    services.duplicate_cv(cv, f"Copy of {cv.name}")
    return redirect("cv_generator:my_cvs")


@login_required
@require_POST
def delete_cv(request, cv_id):
    cv = get_own_cv(request, cv_id)
    if cv.profile.cvs.count() <= 1:
        messages.error(request, "You cannot delete your only CV.")
        return redirect("cv_generator:my_cvs")
    cv.delete()
    return redirect("cv_generator:my_cvs")


@login_required
@require_POST
def activate_cv(request, cv_id):
    cv = get_own_cv(request, cv_id)
    with transaction.atomic():
        cv.profile.cvs.filter(is_active=True).update(is_active=False)
        cv.is_active = True
        cv.save(update_fields=["is_active"])
    return redirect("cv_generator:my_cvs")


@login_required
def download_cv(request, cv_id):
    cv = get_own_cv(request, cv_id)
    if not cv.generated_file:
        raise Http404
    return FileResponse(
        cv.generated_file.open("rb"),
        as_attachment=True,
        filename=f"{cv.name}.pdf",
        content_type="application/pdf",
    )
```

The `builder` URL name is registered in Task 18; until then, point `create_cv`'s redirect at `cv_generator:my_cvs` and switch it to the builder in Task 18 (note this in a `TODO`-free way: just change it in Task 18's steps — it is listed there).

`templates/cv_generator/my_cvs.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="container cv-generator">
  <h1>My CVs</h1>
  <p>
    Build a CV from your publications in KC Works and other repositories,
    plus sections you write yourself. Your <strong>active</strong> CV is
    the one shown on your profile.
  </p>

  <form method="post" action="{% url 'cv_generator:create_cv' %}"
        class="cv-create-form">
    {% csrf_token %}
    <input type="text" name="name" placeholder="Name for a new CV"
           aria-label="Name for a new CV">
    <button type="submit" class="btn btn-primary">Create a CV</button>
  </form>

  <ul class="cv-list">
    {% for cv in cvs %}
      <li class="cv-list-item content-card">
        <div>
          <a href="{% url 'cv_generator:builder' cv.pk %}">
            <strong>{{ cv.name }}</strong>
          </a>
          {% if cv.is_active %}<span class="badge">Active</span>{% endif %}
          {% if cv.generated_at %}
            <small>Generated {{ cv.generated_at|date:"j M Y H:i" }}</small>
          {% endif %}
        </div>
        <div class="cv-actions">
          {% if cv.generated_file %}
            <a href="{% url 'cv_generator:download_cv' cv.pk %}">
              Download PDF</a>
          {% endif %}
          {% if not cv.is_active %}
            <form method="post"
                  action="{% url 'cv_generator:activate_cv' cv.pk %}">
              {% csrf_token %}
              <button type="submit">Make active</button>
            </form>
          {% endif %}
          <form method="post"
                action="{% url 'cv_generator:duplicate_cv' cv.pk %}">
            {% csrf_token %}
            <button type="submit">Duplicate</button>
          </form>
          <form method="post"
                action="{% url 'cv_generator:delete_cv' cv.pk %}"
                onsubmit="return confirm('Delete this CV?');">
            {% csrf_token %}
            <button type="submit">Delete</button>
          </form>
        </div>
      </li>
    {% endfor %}
  </ul>
</div>
{% endblock %}
```

(Check `base.html` for the real content block name — `{% block content %}` here must match what other templates like `edit_profile.html` use; read that file and copy its block usage.) Until Task 18 exists, temporarily link the CV name to `{% url 'cv_generator:my_cvs' %}` so the template renders; Task 18 rewires it to the builder.

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add CV list and lifecycle views"
```

---

### Task 17: Job endpoints — refresh, generate, status, preview

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/views/jobs.py`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/fragments/refresh_status.html`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/fragments/generate_status.html`
- Modify: `knowledge_commons_profiles/cv_generator/urls.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_jobs.py`

**Interfaces:**
- Consumes: `services.start_refresh/start_generation` (Task 14), `classify.counts` (Task 7), `document.render_document` (Task 11), `WORKS_TYPES`.
- Produces URL names:
  - `refresh` (`"refresh/"`, POST) — calls `start_refresh(own_profile)`, returns the refresh-status fragment.
  - `refresh_status` (`"refresh/status/"`, GET) — the fragment: while fetching, a spinner div carrying `hx-get` self-polling every 2s (`hx-trigger="load delay:2s"`, `hx-swap="outerHTML"`); when idle, per-type counts (`counts()` over store records, only for types in `WORKS_TYPES`) + "Publications refreshed <date>"; on error, the message + previous-data note.
  - `generate` (`"<int:cv_id>/generate/"`, POST) → `start_generation`, returns the generate-status fragment.
  - `generate_status` (`"<int:cv_id>/generate/status/"`, GET) — spinner-with-self-poll while generating; on success a "Download PDF" link (and "shown on your profile" note when active); on error the message.
  - `preview` (`"<int:cv_id>/preview/"`, GET) — returns `render_document(cv)` as `text/html` for the builder's preview iframe, with `X-Frame-Options: SAMEORIGIN` left at project default.
- All POST endpoints return the same fragment as their status endpoint (HTMX swaps them into the status region).

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_views_jobs.py`:

```python
"""Refresh/generate/status/preview endpoints (threads mocked)."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.newprofile.models import Profile


class JobViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kcuser", password="pw"
        )
        self.profile = Profile.objects.create(
            name="Test User", username="kcuser"
        )
        self.store = CVWorksStore.objects.create(profile=self.profile)
        self.cv = CurriculumVitae.objects.create(
            profile=self.profile, is_active=True
        )
        self.client.force_login(self.user)

    def test_refresh_starts_job_and_returns_fragment(self):
        with mock.patch.object(
            services, "_spawn"
        ) as spawn:
            response = self.client.post(reverse("cv_generator:refresh"))
        self.assertEqual(response.status_code, 200)
        spawn.assert_called_once()
        self.store.refresh_from_db()
        self.assertEqual(self.store.status, CVWorksStore.STATUS_FETCHING)
        self.assertContains(response, "hx-get")

    def test_refresh_status_shows_counts_when_idle(self):
        self.store.records = [{
            "type": "book", "title": "B", "refereed": "TRUE",
        }]
        self.store.fetched_at = timezone.now()
        self.store.save()
        response = self.client.get(reverse("cv_generator:refresh_status"))
        self.assertContains(response, "Books")
        self.assertContains(response, "1")
        self.assertNotContains(response, "hx-trigger")

    def test_refresh_status_shows_error(self):
        self.store.status = CVWorksStore.STATUS_ERROR
        self.store.error_detail = "KC Works: boom"
        self.store.save()
        response = self.client.get(reverse("cv_generator:refresh_status"))
        self.assertContains(response, "KC Works: boom")

    def test_generate_starts_job(self):
        with mock.patch.object(services, "_spawn") as spawn:
            response = self.client.post(
                reverse("cv_generator:generate", args=[self.cv.pk])
            )
        self.assertEqual(response.status_code, 200)
        spawn.assert_called_once()
        self.cv.refresh_from_db()
        self.assertEqual(
            self.cv.generation_status, CurriculumVitae.STATUS_GENERATING
        )

    def test_generate_status_links_pdf_when_done(self):
        self.cv.generated_file.save("x.pdf", ContentFile(b"%PDF"))
        self.cv.generated_at = timezone.now()
        self.cv.save()
        response = self.client.get(
            reverse("cv_generator:generate_status", args=[self.cv.pk])
        )
        self.assertContains(response, "Download")

    def test_preview_returns_document_html(self):
        CVBlock.objects.create(
            cv=self.cv, kind=CVBlock.KIND_HEADER, position=1
        )
        response = self.client.get(
            reverse("cv_generator:preview", args=[self.cv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")

    def test_other_users_cv_is_404(self):
        other = Profile.objects.create(name="O", username="other")
        cv = CurriculumVitae.objects.create(profile=other)
        response = self.client.get(
            reverse("cv_generator:preview", args=[cv.pk])
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Create stubs and run tests to verify they fail**

`views/jobs.py` with `refresh`, `refresh_status`, `generate`, `generate_status`, `preview` all raising `NotImplementedError`; append to `urls.py`:

```python
    path("refresh/", jobs.refresh, name="refresh"),
    path("refresh/status/", jobs.refresh_status, name="refresh_status"),
    path("<int:cv_id>/generate/", jobs.generate, name="generate"),
    path("<int:cv_id>/generate/status/", jobs.generate_status,
         name="generate_status"),
    path("<int:cv_id>/preview/", jobs.preview, name="preview"),
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement**

`views/jobs.py`:

```python
"""Long-running job endpoints: refresh, generate, status, preview."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVWorksStore,
    WORKS_TYPES,
)
from knowledge_commons_profiles.cv_generator.pipeline.classify import counts
from knowledge_commons_profiles.cv_generator.pipeline.document import (
    render_document,
)
from knowledge_commons_profiles.cv_generator.views.helpers import (
    get_own_cv,
    own_profile,
)

# the builder palette shows these types; the status fragment shows the
# same set so the two never disagree
_LABELS = dict(WORKS_TYPES)


def _refresh_fragment(request, profile):
    store, _ = CVWorksStore.objects.get_or_create(profile=profile)
    type_counts = []
    if store.records:
        for works_type, count in counts(store.records).items():
            if works_type in _LABELS:
                type_counts.append((_LABELS[works_type], count))
    return render(
        request,
        "cv_generator/fragments/refresh_status.html",
        {"store": store, "type_counts": type_counts},
    )


@login_required
@require_POST
def refresh(request):
    profile = own_profile(request)
    services.start_refresh(profile)
    return _refresh_fragment(request, profile)


@login_required
def refresh_status(request):
    return _refresh_fragment(request, own_profile(request))


def _generate_fragment(request, cv):
    return render(
        request,
        "cv_generator/fragments/generate_status.html",
        {"cv": cv},
    )


@login_required
@require_POST
def generate(request, cv_id):
    cv = get_own_cv(request, cv_id)
    services.start_generation(cv)
    return _generate_fragment(request, cv)


@login_required
def generate_status(request, cv_id):
    return _generate_fragment(request, get_own_cv(request, cv_id))


@login_required
def preview(request, cv_id):
    cv = get_own_cv(request, cv_id)
    return HttpResponse(render_document(cv), content_type="text/html")
```

`templates/cv_generator/fragments/refresh_status.html`:

```html
<div id="refresh-status">
  {% if store.status == "fetching" %}
    <div hx-get="{% url 'cv_generator:refresh_status' %}"
         hx-trigger="load delay:2s" hx-swap="outerHTML"
         hx-target="#refresh-status">
      <span class="spinner-border spinner-border-sm" role="status"></span>
      Fetching your publications&hellip; this can take a minute.
    </div>
  {% elif store.status == "error" %}
    <p class="text-danger">
      We could not refresh your publications: {{ store.error_detail }}
      {% if store.records %}Your previously fetched publications are
      still available.{% endif %}
    </p>
  {% else %}
    {% if store.fetched_at %}
      <p>
        Publications refreshed {{ store.fetched_at|date:"j M Y H:i" }}:
        {% for label, count in type_counts %}
          {{ label }}: {{ count }}{% if not forloop.last %} &middot; {% endif %}
        {% endfor %}
      </p>
    {% else %}
      <p>No publications fetched yet &mdash; press
      <strong>Refresh publications</strong>.</p>
    {% endif %}
  {% endif %}
</div>
```

`templates/cv_generator/fragments/generate_status.html`:

```html
<div id="generate-status">
  {% if cv.generation_status == "generating" %}
    <div hx-get="{% url 'cv_generator:generate_status' cv.pk %}"
         hx-trigger="load delay:2s" hx-swap="outerHTML"
         hx-target="#generate-status">
      <span class="spinner-border spinner-border-sm" role="status"></span>
      Generating your PDF&hellip;
    </div>
  {% elif cv.generation_status == "error" %}
    <p class="text-danger">PDF generation failed: {{ cv.error_detail }}</p>
  {% elif cv.generated_file %}
    <p>
      PDF generated {{ cv.generated_at|date:"j M Y H:i" }} &mdash;
      <a href="{% url 'cv_generator:download_cv' cv.pk %}">Download PDF</a>
      {% if cv.is_active %}(also shown on your profile){% endif %}
    </p>
  {% endif %}
</div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add refresh, generation, status and preview endpoints"
```

---

### Task 18: Builder page — canvas, block CRUD, autosave

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/views/builder.py`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/builder.html`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/fragments/block_card.html`
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/js/cv-builder.js`
- Create: `knowledge_commons_profiles/cv_generator/static/cv_generator/css/cv-builder.css`
- Modify: `knowledge_commons_profiles/cv_generator/urls.py`
- Modify: `knowledge_commons_profiles/cv_generator/views/cvs.py` (create_cv redirect → builder) and `templates/cv_generator/my_cvs.html` (CV name links → builder)
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_builder.py`

**Interfaces:**
- Consumes: everything above.
- Produces URL names:
  - `builder` (`"<int:cv_id>/"`, GET) — the three-tab page (this task builds tab 1; tabs 2–3 land in Task 19 as includes into the same template).
  - `save_layout` (`"<int:cv_id>/layout/"`, POST, JSON) — body `{"blocks": [{"id": <int>, "heading": <str>, "content": <str>}, ...]}` in display order. Reorders (position = index+1) and updates heading/content (content sanitized server-side). Unknown/foreign block ids → 400. Returns `{"ok": true}`.
  - `add_block` (`"<int:cv_id>/blocks/add/"`, POST, form fields `kind`, `works_type?`) — appends the block at the end, returns the rendered `block_card.html` fragment (HTMX appends it to the canvas).
  - `delete_block` (`"<int:cv_id>/blocks/<int:block_id>/delete/"`, POST) — returns 200 empty (HTMX removes the card).
- Template contract used by the JS: canvas `<ul id="cv-canvas">`, each card `<li class="cv-block-card" data-block-id="...">` with `.cv-block-heading` input, `.cv-block-content` textarea (TinyMCE-initialised for richtext/footer), `.cv-block-delete` button; palette buttons `.cv-palette-add` with `data-kind` and `data-works-type`; hidden `#cv-builder-config` div with `data-*` URLs and CSRF token.

- [ ] **Step 1: Write the failing tests**

`knowledge_commons_profiles/cv_generator/tests/test_views_builder.py`:

```python
"""Builder page and block-manipulation endpoints."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import CVBlock
from knowledge_commons_profiles.newprofile.models import Profile


class BuilderViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kcuser", password="pw"
        )
        self.profile = Profile.objects.create(
            name="Test User", username="kcuser"
        )
        self.cv = services.ensure_cv_setup(self.profile)
        self.client.force_login(self.user)

    def test_builder_page_renders_blocks_and_palette(self):
        response = self.client.get(
            reverse("cv_generator:builder", args=[self.cv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cv-canvas")
        self.assertContains(response, "Appointments")
        # palette offers every publications type
        self.assertContains(response, "Book chapters")
        self.assertContains(response, "Refresh publications")

    def test_save_layout_reorders_and_updates_content(self):
        blocks = list(self.cv.blocks.all())
        reordered = [blocks[1], blocks[0], *blocks[2:]]
        payload = {
            "blocks": [
                {
                    "id": b.pk,
                    "heading": f"H{i}" if b.kind == "richtext" else b.heading,
                    "content": "<p>text</p><script>x</script>"
                    if b.kind == "richtext" else b.content,
                }
                for i, b in enumerate(reordered)
            ]
        }
        response = self.client.post(
            reverse("cv_generator:save_layout", args=[self.cv.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        fresh = list(self.cv.blocks.all())
        self.assertEqual([b.pk for b in fresh],
                         [b.pk for b in reordered])
        richtext = next(b for b in fresh if b.kind == "richtext")
        self.assertIn("<p>text</p>", richtext.content)
        self.assertNotIn("<script>", richtext.content)

    def test_save_layout_rejects_foreign_blocks(self):
        other_profile = Profile.objects.create(name="O", username="other")
        other_cv = services.ensure_cv_setup(other_profile)
        foreign = other_cv.blocks.first()
        response = self.client.post(
            reverse("cv_generator:save_layout", args=[self.cv.pk]),
            data=json.dumps({"blocks": [
                {"id": foreign.pk, "heading": "", "content": ""}
            ]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_add_block_appends_and_returns_card(self):
        before = self.cv.blocks.count()
        response = self.client.post(
            reverse("cv_generator:add_block", args=[self.cv.pk]),
            {"kind": "publications", "works_type": "book_chapters"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cv.blocks.count(), before + 1)
        new = self.cv.blocks.last()
        self.assertEqual(new.works_type, "book_chapters")
        self.assertContains(response, f'data-block-id="{new.pk}"')

    def test_add_block_rejects_bad_kind(self):
        response = self.client.post(
            reverse("cv_generator:add_block", args=[self.cv.pk]),
            {"kind": "nonsense"},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_block(self):
        block = self.cv.blocks.first()
        response = self.client.post(
            reverse("cv_generator:delete_block",
                    args=[self.cv.pk, block.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CVBlock.objects.filter(pk=block.pk).exists())

    def test_delete_foreign_block_is_404(self):
        other_profile = Profile.objects.create(name="O", username="other")
        other_cv = services.ensure_cv_setup(other_profile)
        foreign = other_cv.blocks.first()
        response = self.client.post(
            reverse("cv_generator:delete_block",
                    args=[self.cv.pk, foreign.pk])
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Create stubs and run tests to verify they fail**

`views/builder.py` with `builder`, `save_layout`, `add_block`, `delete_block` raising `NotImplementedError`; append URL patterns:

```python
    path("<int:cv_id>/", builder.builder, name="builder"),
    path("<int:cv_id>/layout/", builder.save_layout, name="save_layout"),
    path("<int:cv_id>/blocks/add/", builder.add_block, name="add_block"),
    path("<int:cv_id>/blocks/<int:block_id>/delete/",
         builder.delete_block, name="delete_block"),
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement views**

`views/builder.py`:

```python
"""The CV builder page and its block-manipulation endpoints."""

import json

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator.forms import (
    AdvancedOptionsForm,
    IdentityForm,
    RepositoryForm,
)
from knowledge_commons_profiles.cv_generator.models import (
    CVBlock,
    CVWorksStore,
    WORKS_TYPES,
)
from knowledge_commons_profiles.cv_generator.pipeline.classify import counts
from knowledge_commons_profiles.cv_generator.views.helpers import get_own_cv

# palette entries for publications blocks: hide the "all_*" aggregates
# from casual users (they remain valid works_types for saved blocks)
PALETTE_TYPES = [
    (key, label)
    for key, label in WORKS_TYPES
    if not key.startswith("all_")
]


def _type_counts(profile):
    store = getattr(profile, "cv_works_store", None)
    if store is None or not store.records:
        return {}
    return counts(store.records)


@login_required
def builder(request, cv_id):
    cv = get_own_cv(request, cv_id)
    profile = cv.profile
    store, _ = CVWorksStore.objects.get_or_create(profile=profile)
    identity_instance = getattr(profile, "cv_identity", None)

    return render(
        request,
        "cv_generator/builder.html",
        {
            "cv": cv,
            "profile": profile,
            "store": store,
            "blocks": cv.blocks.all(),
            "palette_types": PALETTE_TYPES,
            "type_counts": _type_counts(profile),
            "repositories": profile.cv_repositories.all(),
            "repository_form": RepositoryForm(),
            "advanced_form": AdvancedOptionsForm(instance=cv),
            "identity_form": IdentityForm(
                instance=identity_instance,
                initial={
                    "name": identity_instance.name
                    if identity_instance else "",
                    "orcid": identity_instance.orcid
                    if identity_instance else "",
                    "emails": ", ".join(
                        identity_instance.emails
                    ) if identity_instance else "",
                },
            ),
        },
    )


@login_required
@require_POST
def save_layout(request, cv_id):
    cv = get_own_cv(request, cv_id)

    try:
        payload = json.loads(request.body)
        entries = payload["blocks"]
        ids = [int(entry["id"]) for entry in entries]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Bad payload."},
                            status=400)

    blocks = {b.pk: b for b in cv.blocks.all()}
    if set(ids) != set(blocks):
        return JsonResponse(
            {"ok": False, "error": "Block list does not match this CV."},
            status=400,
        )

    from knowledge_commons_profiles.newprofile.utils import sanitize_html

    with transaction.atomic():
        for position, entry in enumerate(entries, start=1):
            block = blocks[int(entry["id"])]
            block.position = position
            block.heading = (entry.get("heading") or "")[:255]
            if block.kind in (CVBlock.KIND_RICHTEXT, CVBlock.KIND_FOOTER):
                block.content = sanitize_html(entry.get("content") or "")
            block.save(
                update_fields=["position", "heading", "content"]
            )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def add_block(request, cv_id):
    cv = get_own_cv(request, cv_id)
    kind = request.POST.get("kind", "")
    works_type = request.POST.get("works_type", "")

    valid_kinds = dict(CVBlock.KIND_CHOICES)
    valid_types = dict(WORKS_TYPES)
    if kind not in valid_kinds or (
        kind == CVBlock.KIND_PUBLICATIONS and works_type not in valid_types
    ):
        return JsonResponse({"ok": False, "error": "Unknown block type."},
                            status=400)

    last = cv.blocks.last()
    block = CVBlock.objects.create(
        cv=cv,
        kind=kind,
        works_type=works_type if kind == CVBlock.KIND_PUBLICATIONS else "",
        position=(last.position + 1) if last else 1,
    )

    return render(
        request,
        "cv_generator/fragments/block_card.html",
        {"cv": cv, "block": block, "type_counts": _type_counts(cv.profile)},
    )


@login_required
@require_POST
def delete_block(request, cv_id, block_id):
    cv = get_own_cv(request, cv_id)
    block = get_object_or_404(CVBlock, pk=block_id, cv=cv)
    block.delete()
    return HttpResponse("")
```

Also in this task: change `create_cv`'s redirect in `views/cvs.py` to `redirect("cv_generator:builder", cv_id=cv.pk)` and point the CV-name links in `my_cvs.html` at `{% url 'cv_generator:builder' cv.pk %}`.

- [ ] **Step 4: Write the templates and JS**

`templates/cv_generator/fragments/block_card.html`:

```html
<li class="cv-block-card content-card" data-block-id="{{ block.pk }}"
    data-kind="{{ block.kind }}">
  <div class="cv-block-bar">
    <span class="cv-drag-handle" title="Drag to reorder"
          aria-hidden="true">&#8942;&#8942;</span>
    <span class="cv-block-kind">{{ block.get_kind_display }}</span>
    <button type="button" class="cv-block-delete"
            data-delete-url="{% url 'cv_generator:delete_block' cv.pk block.pk %}"
            aria-label="Remove this block">&times;</button>
  </div>

  {% if block.kind == "header" %}
    <p class="cv-block-note">
      Your name, titles, emails and ORCID are filled in automatically
      from your profile. Change them on the Advanced tab.
    </p>
  {% elif block.kind == "publications" %}
    <input type="text" class="cv-block-heading form-control"
           value="{{ block.heading }}"
           placeholder="Heading (leave blank for the default)"
           aria-label="Section heading">
    <p class="cv-block-note">
      {{ block.get_works_type_display }} from your repositories
      {% if type_counts %}
        &mdash; currently
        {{ type_counts|default_if_none:''|dict_get:block.works_type }} items
      {% endif %}
    </p>
  {% else %}
    <input type="text" class="cv-block-heading form-control"
           value="{{ block.heading }}" placeholder="Heading (optional)"
           aria-label="Section heading">
    <textarea class="cv-block-content"
              id="block-content-{{ block.pk }}">{{ block.content }}</textarea>
    {% if block.kind == "footer" %}
      <p class="cv-block-note">
        A &ldquo;Last updated&rdquo; date is added automatically.
      </p>
    {% endif %}
  {% endif %}
</li>
```

The `dict_get` filter does not exist: create
`knowledge_commons_profiles/cv_generator/templatetags/__init__.py` and
`knowledge_commons_profiles/cv_generator/templatetags/cv_extras.py`:

```python
from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """{{ somedict|dict_get:key }} — dictionary lookup by variable key."""
    if not mapping:
        return ""
    return mapping.get(key, "")
```

and use `{% load cv_extras %}` at the top of `block_card.html`, simplifying the count line to `{{ type_counts|dict_get:block.works_type }}`.

`templates/cv_generator/builder.html` (three-tab shell; tabs 2–3 are filled by Task 19 includes — this task renders tab 1 fully and leaves the other two panes containing only their forms' placeholders):

```html
{% extends "base.html" %}
{% load static %}
{% block content %}
<div class="container cv-generator" id="cv-builder"
     data-cv-id="{{ cv.pk }}">
  <div id="cv-builder-config"
       data-save-url="{% url 'cv_generator:save_layout' cv.pk %}"
       data-add-url="{% url 'cv_generator:add_block' cv.pk %}"
       data-csrf="{{ csrf_token }}"></div>

  <h1>{{ cv.name }}</h1>
  <p>
    <a href="{% url 'cv_generator:my_cvs' %}">&larr; All my CVs</a>
    {% if cv.is_active %}<span class="badge">Active CV</span>{% endif %}
  </p>

  <ul class="nav nav-tabs" role="tablist">
    <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab"
        href="#tab-build" role="tab">Build</a></li>
    <li class="nav-item"><a class="nav-link" data-bs-toggle="tab"
        href="#tab-repositories" role="tab">Repositories</a></li>
    <li class="nav-item"><a class="nav-link" data-bs-toggle="tab"
        href="#tab-advanced" role="tab">Advanced</a></li>
  </ul>

  <div class="tab-content">
    <div class="tab-pane active" id="tab-build" role="tabpanel">
      <div class="cv-toolbar">
        <form method="post" action="{% url 'cv_generator:refresh' %}"
              hx-post="{% url 'cv_generator:refresh' %}"
              hx-target="#refresh-status" hx-swap="outerHTML">
          {% csrf_token %}
          <button type="submit" class="btn btn-primary">
            Refresh publications</button>
        </form>
        <button type="button" class="btn btn-secondary" id="cv-preview-btn"
                data-preview-url="{% url 'cv_generator:preview' cv.pk %}">
          Preview</button>
        <form method="post"
              hx-post="{% url 'cv_generator:generate' cv.pk %}"
              hx-target="#generate-status" hx-swap="outerHTML">
          {% csrf_token %}
          <button type="submit" class="btn btn-success">Generate PDF</button>
        </form>
        <span id="cv-save-indicator" aria-live="polite"></span>
      </div>

      {% include "cv_generator/fragments/refresh_status.html" %}
      {% include "cv_generator/fragments/generate_status.html" %}

      <div class="cv-build-layout">
        <aside class="cv-palette">
          <h2>Add a section</h2>
          <button type="button" class="cv-palette-add" data-kind="richtext">
            Rich text</button>
          <button type="button" class="cv-palette-add" data-kind="header">
            Header</button>
          <button type="button" class="cv-palette-add" data-kind="footer">
            Footer</button>
          {% for key, label in palette_types %}
            <button type="button" class="cv-palette-add"
                    data-kind="publications" data-works-type="{{ key }}">
              {{ label }}</button>
          {% endfor %}
        </aside>

        <ul id="cv-canvas">
          {% for block in blocks %}
            {% include "cv_generator/fragments/block_card.html" %}
          {% endfor %}
        </ul>
      </div>

      <div id="cv-preview-modal" hidden>
        <div class="cv-preview-inner">
          <button type="button" id="cv-preview-close">Close preview</button>
          <iframe id="cv-preview-frame" title="CV preview"></iframe>
        </div>
      </div>
    </div>

    <div class="tab-pane" id="tab-repositories" role="tabpanel">
      {% include "cv_generator/fragments/repositories_tab.html" %}
    </div>

    <div class="tab-pane" id="tab-advanced" role="tabpanel">
      {% include "cv_generator/fragments/advanced_tab.html" %}
    </div>
  </div>
</div>
{% endblock %}

{% block javascript %}
  {{ block.super }}
  <script src="{% static 'tinymcelocal/js/tinymce/tinymce.min.js' %}"></script>
  <script src="{% static 'cv_generator/js/cv-builder.js' %}"></script>
  <link rel="stylesheet"
        href="{% static 'cv_generator/css/cv-builder.css' %}">
{% endblock %}
```

Before finalising this template: read `knowledge_commons_profiles/templates/base.html` and `edit_profile.html` to copy the ACTUAL block names (`content`, `javascript`, etc.), the tab markup the project's Bootstrap/Material theme expects (`data-bs-toggle` vs `data-toggle`), and how `edit_profile.html` loads TinyMCE — mirror those exactly. Create the two Task 19 fragment files as empty placeholders (`{# filled in the repositories/advanced task #}`) so this template renders.

`static/cv_generator/js/cv-builder.js`:

```javascript
/* CV builder: drag-to-reorder, palette add, autosave, preview. */
(function ($) {
  "use strict";

  var config = document.getElementById("cv-builder-config");
  if (!config) { return; }

  var saveUrl = config.dataset.saveUrl;
  var addUrl = config.dataset.addUrl;
  var csrf = config.dataset.csrf;
  var indicator = document.getElementById("cv-save-indicator");
  var saveTimer = null;

  function initEditors(root) {
    (root || document)
      .querySelectorAll('.cv-block-card[data-kind="richtext"] textarea,' +
                        ' .cv-block-card[data-kind="footer"] textarea')
      .forEach(function (textarea) {
        if (textarea.dataset.tinymceReady) { return; }
        textarea.dataset.tinymceReady = "1";
        window.tinymce.init({
          target: textarea,
          menubar: false,
          plugins: "lists link",
          toolbar: "bold italic | bullist numlist | link | removeformat",
          setup: function (editor) {
            editor.on("change keyup", scheduleSave);
          },
        });
      });
  }

  function collectBlocks() {
    var blocks = [];
    document.querySelectorAll("#cv-canvas .cv-block-card")
      .forEach(function (card) {
        var textarea = card.querySelector(".cv-block-content");
        var content = "";
        if (textarea) {
          var editor = window.tinymce.get(textarea.id);
          content = editor ? editor.getContent() : textarea.value;
        }
        var heading = card.querySelector(".cv-block-heading");
        blocks.push({
          id: parseInt(card.dataset.blockId, 10),
          heading: heading ? heading.value : "",
          content: content,
        });
      });
    return blocks;
  }

  function saveNow() {
    indicator.textContent = "Saving…";
    fetch(saveUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
      },
      body: JSON.stringify({ blocks: collectBlocks() }),
    }).then(function (response) {
      indicator.textContent = response.ok
        ? "All changes saved."
        : "Could not save — check your connection.";
    }).catch(function () {
      indicator.textContent = "Could not save — check your connection.";
    });
  }

  function scheduleSave() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(saveNow, 800);
  }

  function wireCard(card) {
    var deleteButton = card.querySelector(".cv-block-delete");
    deleteButton.addEventListener("click", function () {
      if (!window.confirm("Remove this section from your CV?")) { return; }
      fetch(deleteButton.dataset.deleteUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
      }).then(function (response) {
        if (response.ok) {
          var textarea = card.querySelector(".cv-block-content");
          if (textarea && window.tinymce.get(textarea.id)) {
            window.tinymce.get(textarea.id).remove();
          }
          card.remove();
          scheduleSave();
        }
      });
    });
    card.querySelectorAll(".cv-block-heading").forEach(function (input) {
      input.addEventListener("input", scheduleSave);
    });
  }

  document.querySelectorAll("#cv-canvas .cv-block-card").forEach(wireCard);
  initEditors(document);

  $("#cv-canvas").sortable({
    handle: ".cv-drag-handle",
    update: scheduleSave,
  });

  document.querySelectorAll(".cv-palette-add").forEach(function (button) {
    button.addEventListener("click", function () {
      var body = new FormData();
      body.append("kind", button.dataset.kind);
      if (button.dataset.worksType) {
        body.append("works_type", button.dataset.worksType);
      }
      fetch(addUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body: body,
      }).then(function (response) {
        return response.text();
      }).then(function (html) {
        var canvas = document.getElementById("cv-canvas");
        canvas.insertAdjacentHTML("beforeend", html);
        var card = canvas.lastElementChild;
        wireCard(card);
        initEditors(card);
        scheduleSave();
      });
    });
  });

  var previewButton = document.getElementById("cv-preview-btn");
  var previewModal = document.getElementById("cv-preview-modal");
  if (previewButton) {
    previewButton.addEventListener("click", function () {
      document.getElementById("cv-preview-frame").src =
        previewButton.dataset.previewUrl;
      previewModal.hidden = false;
    });
    document.getElementById("cv-preview-close")
      .addEventListener("click", function () {
        previewModal.hidden = true;
      });
  }
})(window.jQuery);
```

`static/cv_generator/css/cv-builder.css`:

```css
.cv-build-layout { display: flex; gap: 1.5rem; align-items: flex-start; }
.cv-palette { flex: 0 0 200px; display: flex; flex-direction: column;
              gap: 0.4rem; }
.cv-palette-add { text-align: left; }
#cv-canvas { flex: 1; list-style: none; margin: 0; padding: 0; }
.cv-block-card { margin-bottom: 1rem; padding: 0.75rem; }
.cv-block-bar { display: flex; align-items: center; gap: 0.5rem;
                margin-bottom: 0.5rem; }
.cv-drag-handle { cursor: grab; user-select: none; }
.cv-block-kind { font-weight: 600; flex: 1; }
.cv-block-note { font-size: 0.85rem; color: #555; margin: 0.25rem 0 0; }
.cv-toolbar { display: flex; gap: 0.75rem; align-items: center;
              margin: 1rem 0; flex-wrap: wrap; }
#cv-preview-modal { position: fixed; inset: 0;
                    background: rgba(0, 0, 0, 0.6); z-index: 1050; }
.cv-preview-inner { background: #fff; margin: 3vh auto; width: 90%;
                    height: 94vh; display: flex; flex-direction: column; }
#cv-preview-frame { flex: 1; border: 0; width: 100%; }
@media (max-width: 768px) {
  .cv-build-layout { flex-direction: column; }
  .cv-palette { flex-basis: auto; width: 100%; }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run the test module. Expected: PASS.

- [ ] **Step 6: Visual check with Puppeteer**

Start the dev server, log in as a test user, and use the Puppeteer MCP screenshot tool against the builder page (per the user's web-development workflow: try `https://localhost:443` with self-signed bypass first). Verify: three tabs render; blocks appear as cards with drag handles; palette buttons add cards; TinyMCE loads on rich-text cards; preview modal opens. Iterate until the page is clean and matches the design intent (usable, uncluttered, plain-English labels).

- [ ] **Step 7: Commit**

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add drag-and-drop CV builder with autosave"
```

---

### Task 19: Repositories and Advanced tabs

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/views/repositories.py`
- Create: `knowledge_commons_profiles/cv_generator/views/advanced.py`
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/fragments/repositories_tab.html` (replacing the Task 18 placeholder)
- Create: `knowledge_commons_profiles/cv_generator/templates/cv_generator/fragments/advanced_tab.html` (replacing the Task 18 placeholder)
- Modify: `knowledge_commons_profiles/cv_generator/urls.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_repositories.py`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_advanced.py`

**Interfaces:**
- Consumes: forms (Task 15), models, `builder` view context (Task 18 passes `repositories`, `repository_form`, `advanced_form`, `identity_form`).
- Produces URL names:
  - `add_repository` (`"repositories/add/"`, POST) — validates `RepositoryForm`, appends at the end (position = max+1); on error re-renders the fragment with form errors (HTMX target `#repositories-tab`).
  - `delete_repository` (`"repositories/<int:repo_id>/delete/"`, POST).
  - `move_repository` (`"repositories/<int:repo_id>/move/"`, POST, field `direction` = `up`|`down`) — swaps positions with its neighbour.
  - All three return the re-rendered `repositories_tab.html` fragment.
  - `save_advanced` (`"<int:cv_id>/advanced/"`, POST) — `AdvancedOptionsForm` bound to the CV; `exclude_venues` is edited as one text input per palette works type named `exclude_venues_<works_type>` and reassembled into the JSON dict; returns the re-rendered `advanced_tab.html`.
  - `save_identity` (`"identity/"`, POST) — `IdentityForm` bound to the profile's `CVIdentity` (created on first save); returns the re-rendered `advanced_tab.html`.
- Repository views operate on `own_profile(request)`'s rows only (staff exemption NOT needed here — repositories are edited by their owner in the builder).

- [ ] **Step 1: Write the failing tests**

`tests/test_views_repositories.py`:

```python
"""Repositories tab: add, delete, reorder."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import CVRepository
from knowledge_commons_profiles.newprofile.models import Profile


class RepositoryViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kcuser", password="pw"
        )
        self.profile = Profile.objects.create(
            name="Test User", username="kcuser"
        )
        services.ensure_cv_setup(self.profile)  # creates KC Works repo
        self.client.force_login(self.user)

    def test_add_valid_eprints_repository(self):
        response = self.client.post(
            reverse("cv_generator:add_repository"),
            {"kind": "eprints", "endpoint": "eprints.bbk.ac.uk",
             "label": "Birkbeck"},
        )
        self.assertEqual(response.status_code, 200)
        repo = self.profile.cv_repositories.get(label="Birkbeck")
        # appended after KC Works
        self.assertGreater(
            repo.position,
            self.profile.cv_repositories.get(label="KC Works").position,
        )

    def test_add_internal_url_is_rejected_with_error_shown(self):
        response = self.client.post(
            reverse("cv_generator:add_repository"),
            {"kind": "invenio", "endpoint": "https://10.0.0.1/api/records",
             "label": "Sneaky"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not allowed")
        self.assertFalse(
            self.profile.cv_repositories.filter(label="Sneaky").exists()
        )

    def test_delete_repository(self):
        repo = CVRepository.objects.create(
            profile=self.profile, kind="eprints",
            endpoint="eprints.example.org", position=5,
        )
        self.client.post(
            reverse("cv_generator:delete_repository", args=[repo.pk])
        )
        self.assertFalse(
            CVRepository.objects.filter(pk=repo.pk).exists()
        )

    def test_move_repository_up_swaps_positions(self):
        kc = self.profile.cv_repositories.get(label="KC Works")
        other = CVRepository.objects.create(
            profile=self.profile, kind="eprints",
            endpoint="eprints.example.org", label="E", position=2,
        )
        self.client.post(
            reverse("cv_generator:move_repository", args=[other.pk]),
            {"direction": "up"},
        )
        kc.refresh_from_db()
        other.refresh_from_db()
        self.assertLess(other.position, kc.position)

    def test_cannot_delete_another_users_repository(self):
        other_profile = Profile.objects.create(name="O", username="other")
        repo = CVRepository.objects.create(
            profile=other_profile, kind="eprints",
            endpoint="eprints.example.org",
        )
        response = self.client.post(
            reverse("cv_generator:delete_repository", args=[repo.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CVRepository.objects.filter(pk=repo.pk).exists())
```

`tests/test_views_advanced.py`:

```python
"""Advanced tab: per-CV options and per-user identity overrides."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import CVIdentity
from knowledge_commons_profiles.newprofile.models import Profile


class AdvancedViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kcuser", password="pw"
        )
        self.profile = Profile.objects.create(
            name="Test User", username="kcuser"
        )
        self.cv = services.ensure_cv_setup(self.profile)
        self.client.force_login(self.user)

    def test_save_advanced_options(self):
        response = self.client.post(
            reverse("cv_generator:save_advanced", args=[self.cv.pk]),
            {
                "citation_style": "APA",
                "citation_locale": "en-US",
                "citation_link": "entry",
                "review_of": "Review of",
                "titles_to_italicize": "Cloud Atlas\n2666",
                "exclude_venues_other_articles": "eve.gd, example.org",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.cv.refresh_from_db()
        self.assertEqual(self.cv.citation_style, "APA")
        self.assertEqual(self.cv.citation_locale, "en-US")
        self.assertFalse(self.cv.gold_oa_direct_link)  # unchecked box
        self.assertEqual(
            self.cv.exclude_venues,
            {"other_articles": "eve.gd, example.org"},
        )

    def test_save_identity_creates_override_row(self):
        response = self.client.post(
            reverse("cv_generator:save_identity"),
            {"name": "Dr T. User", "orcid": "0000-0002-1111-2222",
             "emails": "one@example.org, two@example.org"},
        )
        self.assertEqual(response.status_code, 200)
        identity = CVIdentity.objects.get(profile=self.profile)
        self.assertEqual(identity.name, "Dr T. User")
        self.assertEqual(
            identity.emails, ["one@example.org", "two@example.org"]
        )

    def test_invalid_style_shows_error(self):
        response = self.client.post(
            reverse("cv_generator:save_advanced", args=[self.cv.pk]),
            {"citation_style": "NotAStyle", "citation_locale": "en-GB",
             "citation_link": "title", "review_of": "Review of",
             "titles_to_italicize": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.cv.refresh_from_db()
        self.assertEqual(self.cv.citation_style, "MHRA")
```

- [ ] **Step 2: Stubs, URLs, run tests to verify they fail**

Stub the five views (`add_repository`, `delete_repository`, `move_repository` in `views/repositories.py`; `save_advanced`, `save_identity` in `views/advanced.py`) raising `NotImplementedError`; append URL patterns:

```python
    path("repositories/add/", repositories.add_repository,
         name="add_repository"),
    path("repositories/<int:repo_id>/delete/",
         repositories.delete_repository, name="delete_repository"),
    path("repositories/<int:repo_id>/move/",
         repositories.move_repository, name="move_repository"),
    path("<int:cv_id>/advanced/", advanced.save_advanced,
         name="save_advanced"),
    path("identity/", advanced.save_identity, name="save_identity"),
```

Run both test modules. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement views**

`views/repositories.py`:

```python
"""Repositories tab: configure where works are fetched from."""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator.forms import RepositoryForm
from knowledge_commons_profiles.cv_generator.models import CVRepository
from knowledge_commons_profiles.cv_generator.views.helpers import own_profile


def _fragment(request, profile, form=None):
    return render(
        request,
        "cv_generator/fragments/repositories_tab.html",
        {
            "profile": profile,
            "repositories": profile.cv_repositories.all(),
            "repository_form": form or RepositoryForm(),
        },
    )


@login_required
@require_POST
def add_repository(request):
    profile = own_profile(request)
    form = RepositoryForm(request.POST)
    if not form.is_valid():
        return _fragment(request, profile, form)

    repository = form.save(commit=False)
    repository.profile = profile
    last = profile.cv_repositories.last()
    repository.position = (last.position + 1) if last else 1
    repository.save()
    return _fragment(request, profile)


@login_required
@require_POST
def delete_repository(request, repo_id):
    profile = own_profile(request)
    repository = get_object_or_404(
        CVRepository, pk=repo_id, profile=profile
    )
    repository.delete()
    return _fragment(request, profile)


@login_required
@require_POST
def move_repository(request, repo_id):
    profile = own_profile(request)
    repository = get_object_or_404(
        CVRepository, pk=repo_id, profile=profile
    )
    direction = request.POST.get("direction")

    ordered = list(profile.cv_repositories.all())
    index = ordered.index(repository)
    swap_with = None
    if direction == "up" and index > 0:
        swap_with = ordered[index - 1]
    elif direction == "down" and index < len(ordered) - 1:
        swap_with = ordered[index + 1]

    if swap_with is not None:
        with transaction.atomic():
            repository.position, swap_with.position = (
                swap_with.position, repository.position,
            )
            # identical positions would make the swap a no-op; separate
            # them deterministically
            if repository.position == swap_with.position:
                swap_with.position += 1
            repository.save(update_fields=["position"])
            swap_with.save(update_fields=["position"])

    return _fragment(request, profile)
```

(Positions can collide when rows predate ordering edits; after the swap branch, if `repository.position == swap_with.position`, renumber ALL of the profile's repositories sequentially — implement `_renumber(profile)` assigning 1..n in current order and call it before the swap to make swaps always meaningful. Include this `_renumber` helper in the file and call it at the top of `move_repository`; adjust the code above accordingly — simplest correct version: renumber first, reload, then swap.)

`views/advanced.py`:

```python
"""Advanced tab: per-CV options and per-user identity overrides."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator.forms import (
    AdvancedOptionsForm,
    IdentityForm,
)
from knowledge_commons_profiles.cv_generator.models import CVIdentity
from knowledge_commons_profiles.cv_generator.views.builder import (
    PALETTE_TYPES,
)
from knowledge_commons_profiles.cv_generator.views.helpers import (
    get_own_cv,
    own_profile,
)


def _fragment(request, cv, advanced_form=None, identity_form=None):
    profile = cv.profile
    identity = getattr(profile, "cv_identity", None)
    return render(
        request,
        "cv_generator/fragments/advanced_tab.html",
        {
            "cv": cv,
            "profile": profile,
            "palette_types": PALETTE_TYPES,
            "advanced_form": advanced_form or AdvancedOptionsForm(
                instance=cv
            ),
            "identity_form": identity_form or IdentityForm(
                instance=identity,
                initial={
                    "emails": ", ".join(identity.emails) if identity else ""
                },
            ),
        },
    )


@login_required
@require_POST
def save_advanced(request, cv_id):
    cv = get_own_cv(request, cv_id)
    form = AdvancedOptionsForm(request.POST, instance=cv)
    if form.is_valid():
        cv = form.save(commit=False)
        cv.exclude_venues = {
            works_type: request.POST[f"exclude_venues_{works_type}"].strip()
            for works_type, _label in PALETTE_TYPES
            if request.POST.get(f"exclude_venues_{works_type}", "").strip()
        }
        cv.save()
        return _fragment(request, cv)
    return _fragment(request, cv, advanced_form=form)


@login_required
@require_POST
def save_identity(request):
    profile = own_profile(request)
    identity = getattr(profile, "cv_identity", None)
    form = IdentityForm(request.POST, instance=identity)
    cv = profile.cvs.first()
    if form.is_valid():
        identity = form.save(commit=False)
        identity.profile = profile
        identity.save()
        return _fragment(request, cv)
    return _fragment(request, cv, identity_form=form)
```

(`save_identity` needs a CV for the shared fragment; the builder always has at least one via `ensure_cv_setup`. Guard `cv is None` with a 404.)

- [ ] **Step 4: Write the two tab fragments**

`templates/cv_generator/fragments/repositories_tab.html`:

```html
<div id="repositories-tab">
  <h2>Repositories</h2>
  <p>
    Your CV pulls your publications from these places, in order: when the
    same work appears in two repositories, the one higher in this list
    wins.
  </p>

  <ul class="cv-repo-list">
    {% for repo in repositories %}
      <li class="content-card">
        <strong>{{ repo.label|default:repo.endpoint }}</strong>
        <small>({{ repo.get_kind_display }} &mdash;
          {{ repo.endpoint }})</small>
        <span class="cv-repo-actions">
          <form method="post" style="display:inline"
                hx-post="{% url 'cv_generator:move_repository' repo.pk %}"
                hx-target="#repositories-tab" hx-swap="outerHTML">
            {% csrf_token %}
            <input type="hidden" name="direction" value="up">
            <button type="submit" aria-label="Move up">&uarr;</button>
          </form>
          <form method="post" style="display:inline"
                hx-post="{% url 'cv_generator:move_repository' repo.pk %}"
                hx-target="#repositories-tab" hx-swap="outerHTML">
            {% csrf_token %}
            <input type="hidden" name="direction" value="down">
            <button type="submit" aria-label="Move down">&darr;</button>
          </form>
          <form method="post" style="display:inline"
                hx-post="{% url 'cv_generator:delete_repository' repo.pk %}"
                hx-target="#repositories-tab" hx-swap="outerHTML"
                hx-confirm="Remove this repository? Press Refresh afterwards to update your publications.">
            {% csrf_token %}
            <button type="submit" aria-label="Remove repository">
              Remove</button>
          </form>
        </span>
      </li>
    {% endfor %}
  </ul>

  <h3>Add a repository</h3>
  <form method="post" hx-post="{% url 'cv_generator:add_repository' %}"
        hx-target="#repositories-tab" hx-swap="outerHTML">
    {% csrf_token %}
    {{ repository_form.as_p }}
    <p class="cv-block-note">
      For KC Works-style (InvenioRDM) repositories, give the full API
      address, e.g. <code>https://works.hcommons.org/api/records</code>.
      For eprints repositories, the site address is enough, e.g.
      <code>eprints.bbk.ac.uk</code>.
    </p>
    <button type="submit" class="btn btn-primary">Add repository</button>
  </form>
</div>
```

`templates/cv_generator/fragments/advanced_tab.html`:

```html
<div id="advanced-tab">
  <h2>Advanced options</h2>

  <h3>Citations and display (this CV)</h3>
  <form method="post"
        hx-post="{% url 'cv_generator:save_advanced' cv.pk %}"
        hx-target="#advanced-tab" hx-swap="outerHTML">
    {% csrf_token %}
    {{ advanced_form.as_p }}
    <fieldset>
      <legend>Leave out specific venues</legend>
      <p class="cv-block-note">
        Comma-separated venue names to hide from each section.
      </p>
      {% for works_type, label in palette_types %}
        <p>
          <label>{{ label }}:
            <input type="text" name="exclude_venues_{{ works_type }}"
                   value="{{ cv.exclude_venues|dict_get:works_type }}">
          </label>
        </p>
      {% endfor %}
    </fieldset>
    <button type="submit" class="btn btn-primary">Save options</button>
  </form>

  <h3>Your details (all CVs)</h3>
  <p class="cv-block-note">
    Used for the CV header and for finding your work in repositories.
    Pre-filled from your profile; changing them here does not change
    your profile.
  </p>
  <form method="post" hx-post="{% url 'cv_generator:save_identity' %}"
        hx-target="#advanced-tab" hx-swap="outerHTML">
    {% csrf_token %}
    {{ identity_form.as_p }}
    <button type="submit" class="btn btn-primary">Save details</button>
  </form>
</div>
```

Add `{% load cv_extras %}` at the top of `advanced_tab.html`.

- [ ] **Step 5: Run tests to verify they pass**

Run both test modules, plus the builder tests (the placeholder fragments were replaced — the builder page must still render). Expected: PASS.

- [ ] **Step 6: Puppeteer check of both tabs, then commit**

Screenshot the Repositories and Advanced tabs as in Task 18 step 6; iterate until clean.

```bash
git add knowledge_commons_profiles/cv_generator
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add repositories and advanced configuration tabs"
```

---

### Task 20: Edit-profile integration — the tiny links next to the CV field

**Files:**
- Create: `knowledge_commons_profiles/cv_generator/views/integration.py`
- Modify: `knowledge_commons_profiles/cv_generator/urls.py`
- Modify: `knowledge_commons_profiles/templates/newprofile/fragments/cv_edit.html`
- Create: `knowledge_commons_profiles/cv_generator/tests/test_views_integration.py`

**Interfaces:**
- Consumes: `services.start_update_active` (Task 14), `CVWorksStore`/`CurriculumVitae` statuses.
- Produces URL names:
  - `update_active` (`"update-active/"`, POST, JSON) — starts refresh-then-regenerate of the active CV; response `{"ok": true, "started": <bool>}` (`started` False when already running or no active CV — with `"reason"`).
  - `update_active_status` (`"update-active/status/"`, GET, JSON) — `{"state": "working"|"error"|"done"|"none", "detail": <str>, "cv_url": <profile.cv_file.url or "">, "cv_name": <basename or "">}`. `working` while the store is fetching OR the active CV is generating; `error` carries whichever error detail applies.
- `cv_edit.html` gains, inside `#current_cv_section`'s parent, a small actions row: an "Open CV Builder" link to `{% url 'cv_generator:my_cvs' %}` and an "Update publications & regenerate" button that POSTs to `update_active`, then polls `update_active_status` every 2s, reusing the existing `showStatus`/`updateCurrentCv` JS helpers already defined in that fragment.

- [ ] **Step 1: Write the failing tests**

`tests/test_views_integration.py`:

```python
"""Edit-page integration: one-click refresh-and-regenerate."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.newprofile.models import Profile


class UpdateActiveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kcuser", password="pw"
        )
        self.profile = Profile.objects.create(
            name="Test User", username="kcuser"
        )
        self.client.force_login(self.user)

    def test_update_active_starts_job(self):
        services.ensure_cv_setup(self.profile)
        with mock.patch.object(services, "_spawn") as spawn:
            response = self.client.post(
                reverse("cv_generator:update_active")
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["started"])
        spawn.assert_called_once()

    def test_update_active_without_cv_reports_not_started(self):
        response = self.client.post(reverse("cv_generator:update_active"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["started"])

    def test_status_reports_working_then_done(self):
        cv = services.ensure_cv_setup(self.profile)
        store = self.profile.cv_works_store
        store.status = CVWorksStore.STATUS_FETCHING
        store.save()
        state = self.client.get(
            reverse("cv_generator:update_active_status")
        ).json()
        self.assertEqual(state["state"], "working")

        store.status = CVWorksStore.STATUS_IDLE
        store.save()
        cv.generation_status = CurriculumVitae.STATUS_IDLE
        cv.save()
        self.profile.cv_file.save("done.pdf", ContentFile(b"%PDF"))
        state = self.client.get(
            reverse("cv_generator:update_active_status")
        ).json()
        self.assertEqual(state["state"], "done")
        self.assertTrue(state["cv_url"])

    def test_status_reports_error_detail(self):
        cv = services.ensure_cv_setup(self.profile)
        cv.generation_status = CurriculumVitae.STATUS_ERROR
        cv.error_detail = "chromium died"
        cv.save()
        state = self.client.get(
            reverse("cv_generator:update_active_status")
        ).json()
        self.assertEqual(state["state"], "error")
        self.assertIn("chromium died", state["detail"])
```

- [ ] **Step 2: Stubs, URLs, run tests to verify they fail**

Stub `update_active` and `update_active_status` in `views/integration.py` raising `NotImplementedError`; append URLs:

```python
    path("update-active/", integration.update_active, name="update_active"),
    path("update-active/status/", integration.update_active_status,
         name="update_active_status"),
```

Run the test module. Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement views**

`views/integration.py`:

```python
"""Edit-profile integration: one-click update of the active CV."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.cv_generator import services
from knowledge_commons_profiles.cv_generator.models import (
    CVWorksStore,
    CurriculumVitae,
)
from knowledge_commons_profiles.cv_generator.views.helpers import own_profile


@login_required
@require_POST
def update_active(request):
    profile = own_profile(request)
    if not profile.cvs.filter(is_active=True).exists():
        return JsonResponse(
            {"ok": True, "started": False,
             "reason": "No active CV yet — open the CV Builder first."}
        )
    started = services.start_update_active(profile)
    return JsonResponse(
        {"ok": True, "started": started,
         "reason": "" if started else "An update is already running."}
    )


@login_required
def update_active_status(request):
    profile = own_profile(request)
    store = getattr(profile, "cv_works_store", None)
    cv = profile.cvs.filter(is_active=True).first()

    if cv is None:
        return JsonResponse({"state": "none", "detail": "", "cv_url": "",
                             "cv_name": ""})

    if (store and store.status == CVWorksStore.STATUS_FETCHING) or (
        cv.generation_status == CurriculumVitae.STATUS_GENERATING
    ):
        return JsonResponse({"state": "working", "detail": "",
                             "cv_url": "", "cv_name": ""})

    if cv.generation_status == CurriculumVitae.STATUS_ERROR:
        return JsonResponse({"state": "error", "detail": cv.error_detail,
                             "cv_url": "", "cv_name": ""})
    if store and store.status == CVWorksStore.STATUS_ERROR:
        return JsonResponse({"state": "error",
                             "detail": store.error_detail,
                             "cv_url": "", "cv_name": ""})

    cv_url = profile.cv_file.url if profile.cv_file else ""
    cv_name = profile.cv_file.name if profile.cv_file else ""
    return JsonResponse({"state": "done", "detail": "", "cv_url": cv_url,
                         "cv_name": cv_name})
```

- [ ] **Step 4: Wire the edit page**

In `knowledge_commons_profiles/templates/newprofile/fragments/cv_edit.html`, directly after the `</div>` closing `#current_cv_section`, add:

```html
    <div class="cv-generator-links">
      <a href="{% url 'cv_generator:my_cvs' %}" id="open-cv-builder">
        <i class="fas fa-wand-magic-sparkles"></i> Open CV Builder
      </a>
      <button type="button" id="cv-regenerate-btn" class="btn btn-link">
        <i class="fas fa-rotate"></i> Update publications &amp; regenerate
      </button>
    </div>
```

and extend the fragment's existing script (inside the same IIFE, after `attachDeleteHandler();`):

```javascript
    const regenerateBtn = document.getElementById('cv-regenerate-btn');
    const updateUrl = "{% url 'cv_generator:update_active' %}";
    const updateStatusUrl = "{% url 'cv_generator:update_active_status' %}";

    async function pollRegenerate() {
      try {
        const resp = await fetch(updateStatusUrl);
        const state = await resp.json();
        if (state.state === 'working') {
          setTimeout(pollRegenerate, 2000);
        } else if (state.state === 'done') {
          regenerateBtn.disabled = false;
          showStatus('CV regenerated.', 'green', 'fas fa-check-circle');
          if (state.cv_url) {
            updateCurrentCv(state.cv_url, state.cv_name);
          }
        } else {
          regenerateBtn.disabled = false;
          showStatus(
            state.detail || 'Update failed.',
            'red', 'fas fa-exclamation-circle'
          );
        }
      } catch {
        regenerateBtn.disabled = false;
        showStatus('Update failed. Please try again.', 'red',
                   'fas fa-exclamation-circle');
      }
    }

    if (regenerateBtn) {
      regenerateBtn.addEventListener('click', async () => {
        regenerateBtn.disabled = true;
        showStatus('Updating your CV from your repositories…', '#666',
                   'fas fa-spinner fa-spin');
        try {
          const resp = await fetch(updateUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
          });
          const data = await resp.json();
          if (data.started) {
            setTimeout(pollRegenerate, 2000);
          } else {
            regenerateBtn.disabled = false;
            showStatus(data.reason || 'Nothing to update.', '#666',
                       'fas fa-info-circle');
          }
        } catch {
          regenerateBtn.disabled = false;
          showStatus('Update failed. Please try again.', 'red',
                     'fas fa-exclamation-circle');
        }
      });
    }
```

(Check the icon classes against the FontAwesome version the project ships; `fa-sync`/`fa-magic` are the FA5 equivalents if `fa-rotate`/`fa-wand-magic-sparkles` don't render — verify in the Puppeteer step.)

- [ ] **Step 5: Run tests to verify they pass**

Run the integration test module AND the newprofile suite (`knowledge_commons_profiles.newprofile`) — the edited fragment must not break edit-profile tests. Expected: PASS.

- [ ] **Step 6: Puppeteer check, then commit**

Screenshot the edit-profile CV card; confirm the two links render sensibly and the button flow shows status text.

```bash
git add knowledge_commons_profiles/cv_generator knowledge_commons_profiles/templates/newprofile/fragments/cv_edit.html
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add CV builder links and one-click regenerate to profile editing"
```

---

### Task 21: Deployment, docs, final verification

**Files:**
- Modify: `compose/base/Dockerfile` (Chromium for Playwright)
- Modify: `README.md` (feature note under the app docs, if the README documents apps — read it first)
- Create: `docs/cv_generator.md`
- Test: whole suite

**Interfaces:** none new.

- [ ] **Step 1: Docker**

In `compose/base/Dockerfile`'s run stage (`python-run-stage`), after the existing `uv` install lines, add a layer that installs Chromium and its system dependencies via Playwright at build time so containers need no network at runtime:

```dockerfile
# Chromium for CV PDF generation (Paged.js printing via Playwright).
# --with-deps pulls the system libraries Chromium needs on slim images.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN --mount=type=cache,target=/root/.cache/uv \
    uv run --no-project --with playwright \
    playwright install --with-deps chromium \
  && rm -rf /var/lib/apt/lists/*
```

Verify against how the image actually invokes Python (the base Dockerfile syncs deps with `uv sync --frozen`): the invocation must install browsers for the SAME playwright version pinned in `uv.lock` — if `uv run --no-project --with playwright` cannot see the project's pin, instead copy the project in first or run `python -m playwright install --with-deps chromium` after the dependency sync stage. Read the Dockerfile's structure and place the layer where the synced venv exists; `PLAYWRIGHT_BROWSERS_PATH` must be set identically at build and runtime (add it to the runtime ENV too).

Build the dev image to prove it: `docker compose -f docker-compose.dev.yml build django` (or the project's usual build command from the compose files — read `docker-compose.local.yml` to pick the right service name). Expected: build succeeds; image contains `/opt/playwright`.

- [ ] **Step 2: Local Chromium for development**

Document (and run once locally): `uv run playwright install chromium`. Run the Task 12 integration test for real:

```bash
CV_PDF_INTEGRATION=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.local DJANGO_READ_DOT_ENV_FILE=True uv run --group local ./manage.py test knowledge_commons_profiles.cv_generator.tests.test_pipeline_printpdf
```

Expected: PASS including the real-Chromium test.

- [ ] **Step 3: End-to-end smoke test in the browser**

With the dev server running and a logged-in test user: open `/cv/`, press Refresh publications (against the real KC Works API — the test user should be one with works, or accept zero counts), type text into the Appointments block, drag a section, Generate PDF, download it, and confirm the PDF opens with header + sections. Then check the profile edit page shows the generated file and the regenerate button works. Use Puppeteer MCP for the screenshots; iterate on breakage.

- [ ] **Step 4: Write `docs/cv_generator.md`**

Contents: what the feature is (one paragraph); the models and their per-user/per-CV split; how fetching works (strategies, merge order, provenance); how generation works (Paged.js/Playwright, semaphore, UUID files); settings (`CV_KC_WORKS_API`, `CV_RENDER_CONCURRENCY`, `CV_RENDER_TIMEOUT_MS`); deployment note (Chromium layer, `PLAYWRIGHT_BROWSERS_PATH`); how to run the optional integration test. Follow the tone/format of existing docs in `docs/`.

- [ ] **Step 5: Full suite, changelog hygiene, final commit**

Run the FULL test suite. Expected: all pass (existing 1426 + all new).

```bash
git add compose/base/Dockerfile docs/cv_generator.md README.md
pre-commit run --files $(git diff --cached --name-only)
git commit -m "feat(cv): add Chromium to images and document the CV generator"
```

Then rebase on main and stop: per the user's workflow, do NOT push or open a PR until asked. Summarise for the user: what shipped, the one-time `playwright install` step for local dev, and that a GitHub issue number can be retrofitted into the branch name and a GitHub issue comment (per their conventions) before the PR.

---

## Self-Review Notes (already applied)

- **Spec coverage:** models/per-user-vs-per-CV split (T2, T13), UUID cv_file (T3), pipeline port with position-order merge deviation (T4–T8), citeproc-js + project CSL styles (T9–T10), header/richtext/footer/document (T11), Paged.js/Playwright printing with semaphore + timeout (T12), threaded refresh/generate with stalled-status recovery and previous-data preservation (T14), SSRF endpoint validation + sanitize-on-save-and-render (T15, T11, T18), My CVs multi-CV lifecycle with single-active constraint (T2, T16), builder tab with palette/drag/autosave/preview + HTMX polling (T17–T18), repositories + advanced tabs incl. identity overrides pre-filled from profile (T19), edit-page tiny links + one-job refresh-and-regenerate (T20), Docker/browser deployment + docs (T21).
- **Known intentional gaps vs the spec's illustrative ideas:** publications-block citation previews in the builder cards are reduced to live counts (the full preview exists behind the Preview button); drag-from-palette is click-to-add (keyboard-accessible and simpler; canvas drag-to-reorder is real). Both satisfy the spec's usability intent; extend later if the user asks.
- **Type consistency check:** `WORKS_TYPES` names used identically in models, classify constants, palette, and DEFAULT_BLOCKS; `start_*` services return bool; fragments' status string literals match model constants (`"fetching"`, `"error"`, `"generating"` — templates compare against literals, keep them in sync with model constants).
- **Execution notes:** run tasks in order — later tasks import earlier interfaces. eprintsToCV source tree must exist at `$EPRINTSTOCV` during Tasks 4–12. Where a step says "read the file first", that read is mandatory, not optional.






