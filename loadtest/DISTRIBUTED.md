# Running Locust across multiple boxes

When a single load-generator box can no longer push enough RPS at the
target — typically because its CPU is pegged generating traffic, not
because the target is healthy — split the load across two or more boxes
with Locust's built-in distributed mode.

## How distributed Locust talks

One process is the **master** (web UI, ramp control, stats aggregation);
the rest are **workers** (spawn VUs, do the HTTP, ship sample-level
stats back). Workers initiate an outbound TCP connection to the master
on port **5557** (ZeroMQ). The master never connects back. So you need
exactly one firewall rule, on the master box, allowing inbound 5557 from
each worker box.

```
                            ┌──────────────────────────────┐
                            │  Box 1 (master + N workers)  │
   profile.hcommons-test ──►│  mock-oidc, locust-master,   │◄──── 5557 ── Box 2 workers
                            │  N local workers             │◄──── 5557 ── Box 3 workers
                            └──────────────────────────────┘
```

## Box 1 — master + local workers

Already configured in [`docker-compose.loadtest-driver.yml`](docker-compose.loadtest-driver.yml).
The master runs with `network_mode: host`, so port 5557 is exposed on
the host's NIC. The local workers connect at `localhost:5557`.

```bash
LOCUST_HOST=https://profile.hcommons-test.org \
LOCUSTFILE=locustfile_login_only.py \
docker compose -f docker-compose.loadtest-driver.yml \
    up --build --scale locust-worker=8
```

One-off setup:

1. **Security group**: allow inbound TCP **5557** on box 1 from box 2
   and box 3. Private IPs if the boxes share a VPC; public otherwise.
2. **Note box 1's address** that the workers will dial. Private VPC IP
   if available (no public exposure, no egress cost); public IP/DNS
   otherwise.

Optional but recommended: add `--expect-workers <total>` to the master
command so the run waits for every worker (local + remote) to attach
before letting you start. Replace `<total>` with the sum of worker
processes across all boxes.

## Box 2 and Box 3 — workers only

Use [`docker-compose.loadtest-worker.yml`](docker-compose.loadtest-worker.yml).

```bash
git clone <repo> && cd loadtest

# subjects.txt must be present at loadtest/locust/subjects.txt. Copy it
# from box 1 (it's git-ignored — the seed job that built it lives on the
# target deployment).
scp box1:.../loadtest/locust/subjects.txt ./locust/subjects.txt

MASTER_HOST=10.0.1.42 \
LOCUST_HOST=https://profile.hcommons-test.org \
LOCUSTFILE=locustfile_login_only.py \
docker compose -f docker-compose.loadtest-worker.yml \
    up --build --scale locust-worker=8
```

Workers appear in the master UI (port 8089) within a few seconds.
Verify reachability from box 2 first if you suspect a network issue:

```bash
nc -zv <master-host> 5557
```

## Things that bite people

1. **subjects.txt must exist on every worker box.** `_common.py` calls
   `load_subjects()` at module import time on the worker, not the
   master — the master ships a locustfile name, not its contents.
   Different subject lists on different boxes will still drive traffic,
   but they'll skew same-user contention tests specifically.

2. **Locustfile content must match across all boxes.** Same reason as
   above. Easiest pin: identical git revision on every box. If box 2's
   file is a different version, you'll get silent stat divergence.

3. **Locust version must match.** ZeroMQ message format isn't versioned
   defensively across major versions. Building from the same
   `./locust/Dockerfile` and the same git revision guarantees this; the
   `locust>=2.32` pin in `pyproject.toml` alone does not.

4. **mock-oidc on box 1 must already be reachable from the IDMS.**
   This is true regardless of distributed mode — workers just follow
   the `Location` header the IDMS hands them, and the IDMS itself
   calls back to mock-oidc for the token/userinfo exchange. If your
   single-box runs work today, distributed mode adds no new requirement.

5. **Don't conflate "worker processes" with "VUs".** A worker is a
   Python process; one VU is a greenlet inside it. With FastHttpUser,
   a single worker can comfortably drive several hundred greenlet
   VUs. Rule of thumb:

   - **Worker processes per box**: one per CPU core. More than that
     just adds context-switch overhead.
   - **Total VUs**: set in the master UI when starting the test;
     distributed across all attached workers automatically.

   On a 4-core box, `--scale locust-worker=4` and 800 VUs hits much
   higher aggregate RPS than `--scale locust-worker=32` and 800 VUs.

## What changes from the single-box run

- The master's CSV output (`/app/results/run_*.csv`) and the
  `--csv-full-history` data continue to come out of the master box
  only. You don't need to collect anything from the worker boxes.
- The Prometheus exporter on the master (`--prometheus-exporter` if
  enabled via the observability profile) also aggregates across all
  workers — scrape the master, not each worker.
- `MOCK_LATENCY_MS` and the mock-oidc keypair live on box 1; workers
  hit whichever public URL the IDMS hands back, so no per-worker
  configuration of the mock is needed.
