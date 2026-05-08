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

2. **Optional — opt-in observability stack.** Prometheus + Grafana are
   gated behind the `observability` compose profile because they only
   add value when the server-side exporters in
   `docker-compose.loadtest-target.yml` are also running on the test
   deployment. To bring them up:
   ```bash
   docker compose -f docker-compose.loadtest-driver.yml \
     --profile observability up -d
   ```
   Then edit `observability/prometheus.yml` and replace `target-host`
   with the actual hostname or IP of the test deployment, and open
   Grafana at `http://<driver-host>:3000` (anonymous viewer is on; the
   admin password defaults to `loadtest`, override via
   `GRAFANA_ADMIN_PASSWORD`).

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
