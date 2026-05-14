# IDMS Stress Test Suite

A self-contained load test for `knowledge-commons-profiles` that drives the
real CILogon-shaped OIDC flow through a mock IdP. Designed to run against
the test deployment at **`profile.hcommons-test.org`** — never against
production.

## What's in here

```
loadtest/
├── mock_idp/                       # FastAPI mock CILogon
├── locust/                         # Locust scenarios + helpers
├── docker-compose.loadtest-driver.yml
├── docker-compose.loadtest-target.yml
├── observability/
│   ├── prometheus.yml
│   ├── grafana/                    # provisioning + starter dashboard
│   └── postgres_init/              # pg_stat_statements bootstrap SQL
```

The IDMS-side support for load testing lives in the main repo:

* `config/settings/loadtest.py` — settings module that stubs external sync,
  optionally enables `django-prometheus`, and refuses to load on the
  production hostname.
* `knowledge_commons_profiles/loadtest_app/` — tiny app whose `ready()` hook
  monkey-patches `ExternalSync.sync` and the IDMS API client to no-ops.
* `knowledge_commons_profiles/cilogon/management/commands/seed_loadtest_identities.py`
  — `manage.py seed_loadtest_identities --count N | --cleanup`.

## Prerequisites

### On the test deployment host (`profile.hcommons-test.org`)

1. **Enable `pg_stat_statements`** in the RDS parameter group
   (`shared_preload_libraries = pg_stat_statements`). This requires a
   parameter-group switch and an instance reboot — schedule a window. Then
   on the target DB:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   ```
2. **Switch the IDMS container into load-test mode** by setting:
   ```bash
   DJANGO_SETTINGS_MODULE=config.settings.loadtest
   LOADTEST=1
   CILOGON_DISCOVERY_URL=http://<driver-host>:8080/.well-known/openid-configuration
   LOADTEST_PROMETHEUS=1               # optional: enables /metrics
   LOADTEST_STUB_EXTERNAL_SYNC=1       # default
   LOADTEST_STUB_IDMS_API=1            # default
   ```
   in the existing `.envs/.dev/.django` (or via `docker compose run`) and
   restart the Django container.
3. **Run exporters alongside the existing test deployment compose:**
   ```bash
   POSTGRES_EXPORTER_DSN="postgresql://exporter:...@<rds-host>:5432/postgres?sslmode=require" \
   REDIS_EXPORTER_ADDR="redis://<redis-host>:6379" \
   docker compose -f loadtest/docker-compose.loadtest-target.yml up -d
   ```

### On the load-generator (driver) host

1. Build the images and bring up the driver stack:
   ```bash
   cd loadtest
   docker compose -f docker-compose.loadtest-driver.yml build
   docker compose -f docker-compose.loadtest-driver.yml up -d
   ```
   This brings up the mock IdP and Locust master/workers only. Locust's
   own web UI at `http://<driver-host>:8089` shows live RPS, p50/p95/p99
   per named hop, failures, and writes CSVs to `loadtest/results/` —
   enough for verification, ramp, and same-user runs.

For full Prometheus + Grafana observability, follow the runbook in
"Wiring up the observability stack" below.

---

## Wiring up the observability stack

Prometheus + Grafana are deliberately opt-in. They earn their keep when
you're characterising capacity against the real test deployment and want
to correlate Locust client metrics with server-side resource pressure
(Postgres connections, Redis memory, gunicorn worker saturation, host
CPU). For verification or quick ramp runs, Locust's own UI is enough —
skip this section.

### Topology

```
   ┌────────────────────────────── Tester box ────────────────────────────┐
   │                                                                      │
   │   ┌───────────────┐    ┌──────────────┐    ┌────────────────────┐    │
   │   │ mock-oidc     │    │ locust       │    │ prometheus         │    │
   │   │ :8080 (bridge)│    │ :8089/:9646  │    │ :9090 (bridge)     │    │
   │   │               │    │ host network │◄───┤ scrapes everything │    │
   │   └───────────────┘    └──────────────┘    └────────┬───────────┘    │
   │                                                     │                │
   │                                            ┌────────▼─────────┐      │
   │                                            │ grafana :3000    │      │
   │                                            │ queries prom     │      │
   │                                            └──────────────────┘      │
   │                                                                      │
   └──────────────────────────┬───────────────────────────────────────────┘
                              │      HTTPS to /metrics
                              │      SSH-tunneled :9100/:9187/:9121
                              ▼
   ┌────────────────────── Deployment box ────────────────────────────────┐
   │   profile.hcommons-test.org                                          │
   │                                                                      │
   │   IDMS Django (LOADTEST_PROMETHEUS=1, exposes /metrics on :443)      │
   │   node-exporter :9100                                                │
   │   postgres-exporter :9187 (queries RDS Postgres)                     │
   │   redis-exporter :9121 (queries ElastiCache or local Redis)          │
   │                                                                      │
   └──────────────────────────────────────────────────────────────────────┘
```

Key points that often confuse:

* **Grafana queries Prometheus**, not the deployment. Both live in the
  same docker compose on the Tester box; Grafana reaches Prometheus at
  `http://prometheus:9090` via docker-compose service-name DNS — that's
  already configured in `observability/grafana/provisioning/datasources/prometheus.yaml`.
  You never edit that.
* **Prometheus** sits on the bridge network and reaches Locust (which
  runs with `network_mode: host`) via `host.docker.internal:9646`. The
  compose file already has `extra_hosts: host.docker.internal:host-gateway`
  on the prometheus service so this resolves.
* **Prometheus** reaches the IDMS over the public DNS name
  (`profile.hcommons-test.org:443`) — works straight away once
  `LOADTEST_PROMETHEUS=1` is set on the deployment.
* **Prometheus** reaches the host/postgres/redis exporters on the
  deployment box over an SSH tunnel from the Tester box (no need to
  open exporter ports publicly). Tunnel binds those ports on the Tester
  host; Prometheus reaches them via `host.docker.internal`.

### Step 1 — Deployment box: enable `pg_stat_statements`

The parameter to edit is **`shared_preload_libraries`** (a single
comma-separated list), not any of the `pg_stat_statements.*` knobs —
those only take effect once the extension is loaded.

1. RDS console → DB parameter groups. If your instance uses an AWS
   default group (`default.postgres-N`), you can't edit it; create a
   new custom group on the same engine version, then point the instance
   at it under Modify → Apply immediately (or scheduled).
2. In your custom group, find `shared_preload_libraries`. Set the
   value to include `pg_stat_statements` (comma-separate if there are
   already entries).
3. **Reboot the RDS instance.** `shared_preload_libraries` is a static
   parameter; nothing changes until Postgres restarts.
4. Connect to the IDMS database with `psql` and:
   ```sql
   SHOW shared_preload_libraries;             -- expect pg_stat_statements
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   SELECT count(*) FROM pg_stat_statements;   -- 0+ without error
   ```
5. The per-extension knobs (`pg_stat_statements.max`, `.track`, `.save`
   etc.) can stay at defaults; they're tunable as Dynamic parameters
   without a reboot if you ever need to change them.

### Step 2 — Deployment box: create a read-only DB role for postgres-exporter

```sql
CREATE USER prom_exporter WITH PASSWORD '<random>';
GRANT pg_monitor TO prom_exporter;          -- pg ≥ 10
-- For older pg, grant SELECT on pg_stat_database, pg_stat_activity, etc.
```

Compose the DSN you'll feed to the exporter:

```
postgresql://prom_exporter:<password>@<rds-host>:5432/postgres?sslmode=require
```

### Step 3 — Deployment box: turn on the IDMS load-test mode

`django-prometheus` is shipped as an optional dependency in the
`loadtest` group. Install it on the deployment box:

```bash
uv sync --group loadtest
```

(or rebuild the container image with that group if you're running
inside docker.)

Then add (or set, for the duration of a run) to `.envs/.dev/.django`:

```
DJANGO_SETTINGS_MODULE=config.settings.loadtest
LOADTEST=1
CILOGON_DISCOVERY_URL=http://<tester-public-host>:8080/.well-known/openid-configuration
LOADTEST_PROMETHEUS=1
LOADTEST_STUB_EXTERNAL_SYNC=1       # default; explicit for clarity
LOADTEST_STUB_IDMS_API=1            # default; explicit for clarity
```

Restart Django and confirm:

```bash
curl -s https://profile.hcommons-test.org/metrics | head -3
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
# python_gc_objects_collected_total{generation="0"} 12345
```

### Step 4 — Deployment box: bring up the exporters

On the deployment host, alongside the existing IDMS compose:

```bash
cd <repo>/loadtest
POSTGRES_EXPORTER_DSN="postgresql://prom_exporter:...@<rds-host>:5432/postgres?sslmode=require" \
REDIS_EXPORTER_ADDR="redis://<redis-host>:6379" \
docker compose -f docker-compose.loadtest-target.yml up -d

docker compose -f docker-compose.loadtest-target.yml ps
# all three should be 'running' — node-exporter, postgres-exporter, redis-exporter
```

Quick local checks **on the deployment box**:

```bash
curl -fsS localhost:9100/metrics | head -3   # node-exporter
curl -fsS localhost:9187/metrics | head -3   # postgres-exporter
curl -fsS localhost:9121/metrics | head -3   # redis-exporter
```

### Step 5 — Tester box: open SSH tunnels to the exporters

Don't expose the exporter ports publicly — tunnel them. Run this on the
**Tester box**:

```bash
ssh -fN \
  -L 9100:localhost:9100 \
  -L 9187:localhost:9187 \
  -L 9121:localhost:9121 \
  user@profile.hcommons-test.org
```

`-f` backgrounds the SSH process, `-N` says no remote command.
Confirm the tunnels are listening on the Tester:

```bash
ss -tlnp | grep -E ':91(00|87|21)\b'
# 0.0.0.0:9100, 0.0.0.0:9187, 0.0.0.0:9121 should all be LISTEN
```

To kill them later:

```bash
pkill -f 'ssh -fN -L 9100'
```

### Step 6 — Tester box: edit `observability/prometheus.yml`

Open `loadtest/observability/prometheus.yml`. The default targets are
already aligned with this topology — the only thing you may need to
change is the IDMS hostname under `idms-django` if your test deployment
isn't `profile.hcommons-test.org`. The host/postgres/redis jobs already
target `host.docker.internal:910x`, which will reach the SSH-tunneled
ports because the compose file gives prometheus
`extra_hosts: host.docker.internal:host-gateway`.

If your test deployment uses a real LE cert, set
`tls_config.insecure_skip_verify: false` for the `idms-django` job.

### Step 7 — Tester box: bring up the observability stack

```bash
cd <repo>/loadtest
docker compose -f docker-compose.loadtest-driver.yml \
  --profile observability up -d
```

Verify everything Prometheus knows about is up:

```bash
curl -fsS 'http://localhost:9090/api/v1/targets?state=any' \
  | jq '.data.activeTargets[] | {scrapeUrl, health, lastError}'
```

You want every target to show `health: "up"`. Common failures and what
they mean:

| Target down | Cause | Fix |
|---|---|---|
| `idms-django` | `LOADTEST_PROMETHEUS=1` not set, or `/metrics` not in the urlconf | Restart IDMS with the env var; confirm `curl https://profile.hcommons-test.org/metrics` works |
| `idms-host`/`idms-postgres`/`idms-redis` | SSH tunnel not running, or exporters not running on the deployment | `ss -tlnp` on the Tester to verify tunnels; `docker compose ... ps` on the deployment |
| `locust` | Locust isn't exposing Prometheus metrics yet (current scripts don't) | Either ignore (it's a stub), comment out the job, or add a Prometheus listener — see "Adding Locust → Prometheus" below |
| `prometheus` self-scrape | Prometheus not running | `docker compose ... logs prometheus` |

### Step 8 — Tester box: open Grafana

```
http://localhost:3000
```

The dashboard "IDMS Load Test" is auto-provisioned. The Locust row will
be empty unless you've added a Prometheus listener to Locust (see
below); the Django/Postgres/Redis/Host rows should be live as soon as
the corresponding targets show `up` in step 7.

### Adding Locust → Prometheus (optional)

The locustfiles in this repo do not currently expose Prometheus metrics
out of the box. Three options:

1. **`locust --prometheus`**: Locust 2.30+ has a `--prometheus-listener`
   plugin shipped via `locust-plugins`. Add `locust-plugins` to
   `loadtest/locust/pyproject.toml`, append `--prometheus-listener` to
   the master command in the compose file, and rebuild.

2. **`prometheus-client` listener**: add `prometheus_client` to
   `loadtest/locust/pyproject.toml` and a small listener in `_common.py`
   that hooks `request` events and exposes `/metrics` on port 9646.
   ~30 lines.

3. **Skip it**: Locust's own web UI at `:8089` already shows the
   client-side latency/RPS data Prometheus would surface. Comment out
   the `locust` job in `prometheus.yml`. The Grafana Locust row stays
   empty but everything else works fine.

### Tearing down

```bash
# Tester box
docker compose -f docker-compose.loadtest-driver.yml down
pkill -f 'ssh -fN -L 9100'

# Deployment box — stop the exporter sidecar but leave Django running
docker compose -f loadtest/docker-compose.loadtest-target.yml down

# Then on the IDMS, unset LOADTEST_* and DJANGO_SETTINGS_MODULE=config.settings.loadtest
# from .envs/.dev/.django and restart Django to return to normal operation.
```

---

## Seeding identities

On the test deployment host:

```bash
LOADTEST=1 ./manage.py seed_loadtest_identities --count 2000
# writes /tmp/loadtest_subjects.txt
```

Copy that file to the driver host (or a shared volume) and point
`LOADTEST_SUBJECTS_HOST` at it before bringing the driver stack up:

```bash
LOADTEST_SUBJECTS_HOST=/path/to/loadtest_subjects.txt \
docker compose -f docker-compose.loadtest-driver.yml up -d
```

When you're done with a run sequence:

```bash
LOADTEST=1 ./manage.py seed_loadtest_identities --cleanup
```

## Running a scenario

Pick a locustfile via the `LOCUSTFILE` env var when starting the driver
stack, e.g.

```bash
LOCUSTFILE=locustfile_mixed.py \
LOCUST_HOST=https://profile.hcommons-test.org \
docker compose -f docker-compose.loadtest-driver.yml up -d locust-master
docker compose -f docker-compose.loadtest-driver.yml up -d --scale locust-worker=4 locust-worker
```

Then open `http://<driver-host>:8089` and start the run.

| File | Purpose |
|---|---|
| `locustfile_login_only.py` | Pure login throughput; finds the logins/sec ceiling. |
| `locustfile_mixed.py` | 95% browse / 5% login; realistic shape. |
| `locustfile_same_user.py` | Pool of 10 subjects hammered by every VU; validates `select_for_update` upsert. |
| `locustfile_broker.py` | Cross-app SSO via `?return_to=…` and back-channel nonce verify. |
| `locustfile_soak.py` | Steady mixed load, designed for 4–6h soak. |
| `locustfile_profile.py` | Profile-page workload — shell + 7 HTMX fragments per view. Anonymous by default; set `PROFILE_REQUIRE_LOGIN=1` to log VUs in first. |

## Test sequence

| # | Test | Locustfile | Users | Duration |
|---|---|---|---|---|
| 1 | Smoke | login_only | 1 | 2m |
| 2 | Baseline | mixed | 50 | 10m |
| 3 | Login throughput ramp | login_only | 0 → 500 | 30m |
| 4 | Mixed-traffic stress | mixed | 0 → 2000 | 30m |
| 5 | Login spike | login_only | 100 → 1000 step | 10m |
| 6 | Same-user contention | same_user | 100 / 10 subs | 10m |
| 7 | Broker flow | broker | 200 | 15m |
| 8 | Soak | soak | ~70% of #4 knee | 6h |

Between major scenarios, `SELECT pg_stat_statements_reset();` and snapshot
Grafana so the diff is meaningful.

## Safety

* The seed command refuses to run unless `LOADTEST=1` AND the resolved
  hostname is in the allowlist. `profile.hcommons.org` is rejected
  unconditionally.
* `config/settings/loadtest.py` refuses to load on `profile.hcommons.org`
  (override only with `LOADTEST_ALLOW_PRODUCTION_HOSTNAME=1`, which you
  should never do).
* External sync (Mailchimp/MLA/ARLISNA/UP/ROR) and the IDMS event API are
  monkey-patched to no-ops by `loadtest_app`. Verify by tailing logs after
  startup — you should see two `WARNING` lines about the stubs being
  installed.

## Verification before declaring the suite usable

1. **Mock health.** `curl http://<driver>:8080/.well-known/openid-configuration`
   returns valid JSON; `/.well-known/jwks.json` returns a key whose `kid`
   matches the `kid` header in any subsequently issued ID token.
2. **End-to-end login.** With the IDMS in load-test mode, hit
   `https://profile.hcommons-test.org/login/?login_hint=loadtest_0000` in a
   browser/`curl --cookie-jar` and confirm you land at `/my-profile/` with a
   sessionid cookie. Log inspection: no `ExternalSync.sync` invocation, no
   IDMS API client outbound calls.
3. **Cleanup correctness.** `--cleanup` followed by:
   `User.objects.filter(username__startswith="loadtest_").count() == 0`,
   same for `Profile`, `SubAssociation`,
   `TokenUserAgentAssociations.objects.filter(user_name__startswith="loadtest_")`.
4. **Locust smoke (#1).** 1 VU, 2 minutes, login_only. Stats table shows 5
   named rows (`01 /login`, `02 IdP /authorize`, `03 /cilogon/callback`,
   `04a /my-profile`, `05 /logout`) with zero failures.
5. **Same-user contention (#6).** 100 VUs / 10 subs / 10 min. Post-run:
   exactly 10 `User` rows starting with `loadtest_`; zero 5xx in the Locust
   failure log.
6. **Dashboard live.** During the smoke run all six rows of the Grafana
   dashboard show data.
7. **Soak shutdown clean.** After 6h, `--cleanup` removes everything;
   `pg_stat_statements` shows no orphaned long-running queries.
