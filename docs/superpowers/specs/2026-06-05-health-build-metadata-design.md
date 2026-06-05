# Self-Reporting Health Endpoints & Branch-Aware Build Tags

Issue: #609

## Problem

The health endpoints don't expose enough detail to tell which branch, commit,
or container image is deployed in a given environment. Today `/health/` shows
only `VERSION` (from `__version__.py`) and `/broker/health/` shows only
`{"status": "ok"}`. There is no way to map a running instance back to its exact
source commit or to the image that was pushed for it.

Separately, the dev build tag (`v<version>-<sha>`) is not branch-qualified, so
builds of the same version produced on different branches would collide on a
single Docker tag.

## Design

Adopt two conventions from the sibling `commons-wordpress` pipeline, keeping the
existing single-`ci.yml` / `docker compose build` structure intact (no move to
separate prepare/build jobs, no `docker/build-push-action`).

### 1. Branch-aware build tag (CI)

The build tag becomes branch-qualified on non-main branches; `main` keeps the
canonical unprefixed form so it stays the owner of the release version line.

| Branch | `BUILD_TAG` |
|--------|-------------|
| `main` | `v${VERSION}-${SHORT_SHA}` (unchanged) |
| `dev`  | `dev-v${VERSION}-${SHORT_SHA}` |

Only `deploy-dev`'s `build=` computation changes (prefix with
`${GITHUB_REF_NAME}-`). `release-main` is main-only and already emits the
unprefixed form. The tag continues to be used as the pushed Docker tag, so each
branch now gets a uniquely named image instead of racing for one tag.

### 2. Bake deploy metadata into the image (build-args -> ENV)

Three build-args flow CI -> compose `build.args` -> Dockerfile `ARG`->`ENV`, so
the running container self-reports with no ECS task-definition change. On ECS
the image `ENV` is the base layer the task launches with; the S3 env-file and
the task-def `environment` block do not define these keys, so the baked values
pass straight through to the process. This is the same mechanism the entrypoint
already relies on for `BUILD_ENV`.

| Build arg | CI source | Surfaced as |
|-----------|-----------|-------------|
| `APP_BRANCH` | `github.ref_name` | branch |
| `BUILD_TAG`  | the branch-aware tag above | image |
| `GIT_SHA`    | full SHA of the built commit¹ | SHA |

¹ `release-main` builds *after* the `cz bump` commit, so `GIT_SHA` is the
post-bump HEAD (`bump_commit.sha`), consistent with the short SHA inside
`BUILD_TAG`. `deploy-dev` uses `github.sha` (no bump there).

`APP_VERSION` is intentionally NOT baked. The version already lives in
`__version__.py` (copied into the image, already shown by `/health/`); a second
source of truth would only risk drift, and `BUILD_TAG` already encodes it.

### 3. Settings (`config/settings/base.py`)

```python
GIT_SHA = env("GIT_SHA", default="unknown")
BUILD_TAG = env("BUILD_TAG", default="unknown")
APP_BRANCH = env("APP_BRANCH", default="unknown")
```

Read once at settings load and inherited by production / dev / idms / local /
test. Off-CI (local dev, test runs) they default to `"unknown"`.

### 4. Health endpoints

Both endpoints gain three keys alongside the existing `VERSION`:

- `/health/` (`newprofile/views/health.py`): `Branch`, `Image`, `SHA` read from
  `settings`.
- `/broker/health/` (`cilogon/broker_views.py`): the same three keys merged into
  its JSON response.

Adding keys is backward-compatible; the existing status-code logic is unchanged.
`GIT_SHA` (full, 40 chars) and the short SHA inside `BUILD_TAG` (7 chars) share a
prefix by design.

## Files changed

- **Modified:** `.github/workflows/ci.yml` — branch-aware `build=` in
  `deploy-dev`; `APP_BRANCH` / `BUILD_TAG` / `GIT_SHA` exported on both build
  steps.
- **Modified:** `docker-compose.production.yml`, `docker-compose.dev.yml` — three
  build-args on the `django` and `idms` services.
- **Modified:** `compose/{production,dev}/{django,idms}/Dockerfile` — `ARG` +
  `ENV` block (×4).
- **Modified:** `config/settings/base.py` — three env reads.
- **Modified:** `knowledge_commons_profiles/newprofile/views/health.py`,
  `knowledge_commons_profiles/cilogon/broker_views.py`.
- **Tests:** `newprofile/tests/test_health.py`,
  `cilogon/tests/test_broker_idms.py`.

## Out of scope (kept as-is)

- No restructuring of `ci.yml`; no move off `docker compose build`.
- commitizen bump flow unchanged.
- No `APP_VERSION` baking; no ECS task-definition edits.
- "image" = the build tag (per decision), not a full `registry/repo:tag`
  reference.

## Testing

Behavioural, red -> green (CI YAML, compose, and Dockerfiles are not
unit-testable, so they are verified by review):

- `/health/`: `override_settings` for the three values; assert the JSON surfaces
  them.
- `/broker/health/`: assert the three keys appear in the response.
