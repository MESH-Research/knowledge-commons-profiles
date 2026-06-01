# Async IDMS broker service

This document explains why the silent-SSO broker runs as a separate
asynchronous service ("IDMS"), how it is wired together, and — most importantly
— the **hosting and operational implications** of running it. It is the
reference for anyone deploying, scaling, or changing the broker.

Tracking issue: [#605](https://github.com/MESH-Research/knowledge-commons-profiles/issues/605).

---

## 1. Why this exists

When the silent SSO broker is enabled, `hcommons.org` bounces a large share of
pageviews to `https://profile.hcommons.org/broker/silent-login/`. Each of those
redirects is cheap on its own, but they land on the **same** Gunicorn worker
pool as the heavy profile pages:

- Production Gunicorn: `gthread`, **5 workers × 8 threads = 40 concurrent
  requests**, `--timeout 15`.
- `ATOMIC_REQUESTS = True` globally, so **every** request — including an
  anonymous broker redirect that runs zero ORM queries — opens a Postgres
  transaction and holds a connection for the request's lifetime.

Under a redirect storm the 40-thread pool saturates, the trivial broker
redirects queue behind slow profile work and die at the 15-second timeout, and
502s cascade across the whole site. The broker view itself is already lean
(anonymous path: validate + 302; authenticated path: one indexed
`SubAssociation` lookup + a Redis nonce write) and already skips the expensive
custom middleware (issues #590 / #591).

**The problem is runtime isolation, not broker latency.** The `cilogon`
(login/IDMS/broker) and `newprofile` (profiles) Django apps are already separate
in code; what was missing is a separate *process* so the broker cannot be
starved by the profiles workload.

## 2. The decision

Serve the broker endpoints from a standalone **asynchronous ASGI service**
("IDMS") running under uvicorn, in its **own container/image and its own ECS
task**, path-routed on the same host as the profiles app.

Because the broker is almost entirely I/O-bound, a single async worker can hold
thousands of concurrent, in-flight silent-login redirects without consuming a
thread per request — the opposite of the synchronous `gthread` model. It also
scales independently of the profiles site.

### Alternatives considered and rejected

| Option | Why rejected |
|---|---|
| **Just add Gunicorn workers** | Raises the ceiling but the broker still shares the pool and connection budget with profiles; a profiles slowdown still starves it. Doesn't solve isolation. |
| **Move the whole app to ASGI** | Works (Django runs sync views in a threadpool under ASGI) but is a large, whole-surface migration: `ATOMIC_REQUESTS`, sync/async middleware adapter hops on the 4 custom middlewares, thread-sensitivity tuning, DRF/authlib sync paths — a big test burden to speed up one endpoint. |
| **Rewrite the broker in FastAPI/Starlette** | Highest raw throughput, but would duplicate security-critical logic: Django session decoding (`cached_db`), the auth check, AES payload encryption, the nonce store. High risk of drift. The same DB alone wouldn't relieve connection pressure either. |
| **Split the broker into a new Django app** | The apps are *already* separate; this buys nothing. The missing isolation is at the process/runtime level. |

The chosen approach keeps the security-critical crypto/validation in one place
(`cilogon/oauth.py`, reused unchanged via `sync_to_async`) while getting both
async throughput and process isolation, with the broker URLs and the main app
left untouched.

## 3. Architecture

```
Browser (already has a session cookie for profile.hcommons.org)
   │
hcommons.org ──302──► profile.hcommons.org/broker/silent-login/?return_to=…
   │                               │
   │                       Traefik (web entrypoint)
   │        broker-router:  Host(…) && PathPrefix(`/broker/`), priority 1000
   │                               │
   │                               ▼
   │                  IDMS container — uvicorn / ASGI
   │                  • async silent_login / verify_broker_nonce / health
   │                  • slim middleware: Security + Session + Auth
   │                  • shares SECRET_KEY + Redis + Postgres with the main app
   │                               │
   ◄──302 return_to?broker_token=… ┘

every other path ──► Traefik web-router ──► django container (unchanged WSGI app)
```

The IDMS image is built from the **same codebase** as the django image (so every
transitive import resolves), differing only in entrypoint (uvicorn vs gunicorn)
and settings module.

### Code layout

| Path | Role |
|---|---|
| `knowledge_commons_profiles/cilogon/broker_views.py` | Async `silent_login`, `verify_broker_nonce`, `broker_health`, and minimal JSON `broker_404` / `broker_500` handlers. Reuses `build_broker_redirect` / `validate_return_to` from `cilogon/oauth.py` via `sync_to_async`. |
| `config/broker_urls.py` | Minimal URLconf — only the broker paths (identical strings) + health; sets `handler404` / `handler500`. |
| `config/asgi.py` | ASGI entrypoint (`application = get_asgi_application()`). |
| `config/settings/idms_overrides.py` | `apply_idms_overrides(globals())` — the shared lean-broker profile. |
| `config/settings/idms.py` | Inherits **production** + applies the overrides. |
| `config/settings/idms_dev.py` | Inherits **dev** + applies the overrides. |
| `compose/{production,dev}/idms/` | Dockerfile + entrypoint + start (uvicorn). |
| `aws/idms-task-definition.json`, `aws/deploy-idms.sh` | ECS Fargate task + deploy script. |

The main app's `cilogon/views.py` (sync broker views) and `cilogon/urls.py` are
**deliberately untouched** — see §6.

## 4. Hosting & deployment implications

### 4.1 One process per container, one image per environment

IDMS is its own image and its own container/task — never a second process inside
the django container. There is a production image (`compose/production/idms/`,
`BUILD_ENV=production`) and a dev image (`compose/dev/idms/`, `BUILD_ENV=dev`).
Both run `uvicorn config.asgi:application` on **port 8000**.

The uvicorn dependencies (`uvicorn[standard]`, `psycopg-pool`) live in the
**production** dependency group in `pyproject.toml`. The dev group includes the
production group, so both images get them.

### 4.2 Shared state — the correctness backbone

IDMS reads the session the user already established by logging in on the
profiles site, and verifies nonces minted by the main app. It therefore **must**
share, per environment:

- **`DJANGO_SECRET_KEY`** — session-cookie signing. A mismatch means IDMS cannot
  read any session (every silent-login returns `no_session`).
- **The session store** — Redis *and* Postgres (`SESSION_ENGINE = cached_db`).
- **`STATIC_API_BEARER`** — the AES key for broker tokens and the bearer for
  `verify-nonce`.
- **Redis `default`** — the nonce written by `build_broker_redirect` (in IDMS
  *and* in the main app's `callback`) is read by `verify-nonce` (IDMS).

In Compose this is achieved by sharing the same env file (`./.envs/.production/.django`
or `./.envs/.dev/.django`); on ECS the task loads the **same** environment as the
django task and only overrides `DJANGO_SETTINGS_MODULE` (see `aws/idms-task-definition.json`).

### 4.3 Same host, path-routed

The session cookie is host-scoped, so IDMS must answer on the **same hostname**
the user logged in on. Routing is therefore **path-based**, not host-based:
Traefik's `broker-router` matches `(Host(…) || …) && PathPrefix(/broker/)` and
forwards to the `idms` service (`http://idms:8000`).

- `priority: 1000` — must exceed `web-router`'s length-derived default so
  `/broker/*` wins while every other path falls through to django.
- The `Host(...)` rule is **replicated** from `web-router` per environment:
  - Production: `profile.hcommons.org`, `www.profile.hcommons.org`,
    `profile.hcommons-test.org`, `www.profile.hcommons-test.org`.
  - Dev: `profile.hcommons-dev.org`, `www.profile.hcommons-dev.org`.

> If you ever move IDMS to its own subdomain instead of path-routing, the
> session cookie will **not** be sent unless `SESSION_COOKIE_DOMAIN` is widened
> to a shared parent (e.g. `.hcommons.org`) on *both* apps. Path routing on the
> same host avoids this entirely.

### 4.4 Database: no transaction, bounded pool

`config/settings/idms_overrides.py` sets, for the broker DB:

- `ATOMIC_REQUESTS = False` — the broker needs no request-level transaction (a
  read plus a cache write), and wrapping the anonymous redirect storm in
  transactions would pointlessly hold connections.
- `CONN_MAX_AGE = 0` and `OPTIONS["pool"] = {min_size, max_size, timeout}`
  (defaults 2 / 10 / 10, tunable via `IDMS_DB_POOL_*` env vars). The bounded
  psycopg pool caps IDMS's Postgres footprint regardless of concurrency. psycopg
  v3 (already used) requires `CONN_MAX_AGE = 0` when pooling.

Note: Django's async ORM still runs the actual query on a thread, so the
**authenticated** path's single lookup is thread-bound (and pool-bounded). The
**anonymous** path — the bulk of the storm — is pure event-loop work with no DB
or thread at all.

### 4.5 Slim middleware

IDMS runs only `SecurityMiddleware`, `SessionMiddleware`, `AuthenticationMiddleware`
(all async-capable). The main app's custom middlewares (token refresh, garbage
collection, referer-nav) already skip the broker paths, so dropping them keeps
the hot path free of sync/async adapter hops.

### 4.6 Scaling

`UVICORN_WORKERS` (default 2) sets the number of event-loop worker processes per
container — size it roughly to the task's vCPUs. Scale further by raising the
ECS service desired count (horizontal). Because the broker is I/O-bound, a small
number of containers absorbs very high redirect volume.

### 4.7 Health check

`GET /broker/health/` returns 200 when Redis and Postgres are reachable, 500
otherwise. It backs both the ECS container health check and any load-balancer
target-group check.

## 5. Operating it

### Deploy / cutover (safe order)

1. Build + push the IDMS image (`aws/deploy-idms.sh` for production; the dev
   stack builds the `idms` service from `docker-compose.dev.yml`).
2. Start the IDMS task/container and confirm it is healthy via `/broker/health/`.
3. **Last:** enable the Traefik `broker-router` so `/broker/*` shifts to IDMS.

### Rollback

Remove (or lower the priority of) the `broker-router` rule. `/broker/*` then
falls back to the main app, which still serves the broker via its synchronous
views. This is an **instant, zero-deploy rollback**.

## 6. Gotchas (read before changing the broker)

- **Broker URLs are a frozen external contract.** `WordPress` and `Works`
  hardcode `/broker/silent-login/` and `/broker/verify-nonce/`. Do not rename or
  move them. This is why `config/urls.py` and `cilogon/urls.py` are untouched and
  IDMS serves the *same* path strings.
- **The broker is dual-served.** The main app still serves `/broker/*` via the
  **synchronous** views in `cilogon/views.py` (used in local dev and as the
  rollback fallback); IDMS serves the **asynchronous** views in
  `cilogon/broker_views.py`. A change to broker behaviour must be made in (or
  coordinated across) **both**. The shared crypto/validation lives once in
  `cilogon/oauth.py`.
- **`SECRET_KEY` rotation and session-backend changes must be applied to IDMS
  and the main app together**, or IDMS silently stops reading sessions.
- **`DJANGO_SETTINGS_MODULE` is forced by the IDMS `start` script** (to
  `config.settings.idms` / `idms_dev`) because the shared env file sets it to
  `production` / `dev` for the main app.
- **IDMS cannot render the project's HTML error pages** — they reverse main-app
  URL names that don't exist in `config.broker_urls`. That is why the broker
  URLconf installs minimal JSON `handler404` / `handler500`.
- **Async data access only.** Async views must use `await request.auser()`,
  `.afirst()`, `cache.aget/adelete`, and `sync_to_async(...)` for sync helpers /
  session reads — never the sync ORM/user/session directly, or uvicorn raises
  `SynchronousOnlyOperation`. The test suite exercises the views under a real
  event loop (`AsyncClient`) precisely to catch this.

## 7. Local development

You do **not** need to run IDMS locally. The local stack runs only the main
django app, which still serves `/broker/*` through its synchronous views. IDMS
matters only where Traefik path-routing is in play (the dev and production
stacks).

## 8. Companion change (separate work)

The highest-leverage reduction is at the *source*: the WordPress side should fire
silent-login at most once per session and cache the `no_session` result, so the
broker is not hit on every pageview. That lives in a different repository and is
tracked separately. The IDMS isolation here makes the broker resilient to the
volume; the throttle reduces the volume.

## 9. Testing

- Unit/behaviour: `knowledge_commons_profiles/cilogon/tests/test_broker_idms.py`
  (run via `uv run ./manage.py test`) covers the async views through
  `config.broker_urls`, routing isolation, the health probe, and a real
  event-loop (`AsyncClient`) pass.
- Load: point `loadtest/locust/locustfile_broker.py` at a test deployment and
  confirm the broker sustains the target RPS with the profiles app under
  concurrent load without the 502/timeout cascade.
