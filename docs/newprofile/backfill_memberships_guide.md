# Backfilling Membership Data (`backfill_memberships`)

## Background

Network membership listings (`/network/<network_name>/members/`) and
other membership-dependent features read the materialized
`Profile.is_member_of` JSON. That field is only written when a profile
passes through `ExternalSync` — which happens on:

- CILogon login and account association
- a fetch of the user through the REST profile-detail endpoint
- society enrolment flows
- an `import_comanage` run that touches the profile

Members who have never triggered any of those have `is_member_of`
`NULL` and are invisible to network listings, even when their local
`Role` rows (or the external partner APIs) say they are members.
Manual `role_overrides` are applied at read time regardless, but
API/COmanage-derived membership must be materialized.

The `backfill_memberships` management command fills this gap.

## Modes

### Local mode (default)

Recomputes the societies in `settings.KNOWN_SOCIETY_MAPPINGS` (the
COmanage-derived networks, e.g. STEMED+ and HASTAC) from local `Role`
rows via `ExternalSync.refresh_local_memberships`. Makes **no external
API calls**. Existing keys for non-COmanage societies (e.g. MLA, MSU)
are preserved.

```bash
# preview which profiles would be processed; writes nothing
uv run ./manage.py backfill_memberships --dry-run

# materialize memberships for never-synced profiles only
uv run ./manage.py backfill_memberships --missing-only

# recompute mapped societies for every profile (corrects stale values)
uv run ./manage.py backfill_memberships
```

### Full mode (`--full`)

Runs the complete `ExternalSync.sync` per profile, which also queries
the external partner APIs (`settings.EXTERNAL_SYNC_CLASSES`: MLA, MSU,
ARLISNA, UP). This is slow and rate-limited by the partners — use
`--sleep` to pause between profiles. The `SYNC_HOURS` cache is
respected, so recently synced profiles are skipped cheaply; pass
`--force` to re-sync them anyway.

```bash
uv run ./manage.py backfill_memberships --full --sleep 1
```

## Options

| Option | Effect |
|--------|--------|
| `--full` | Run the complete external sync per profile instead of the local-only refresh. |
| `--force` | With `--full`: ignore the `SYNC_HOURS` cache. |
| `--missing-only` | Only process profiles with no sync data at all (`is_member_of` NULL or empty). |
| `--username NAME` | Process a single profile. |
| `--sleep N` | Pause N seconds between profiles (rate-limits partner APIs in `--full` mode). |
| `--no-notify` | Do not ping `WEBHOOK_URLS` for changed profiles. |
| `--dry-run` | Report what would be processed; write nothing, notify nobody. |
| `--state-file PATH_OR_URI` | Record progress for resumption (see below). |
| `--checkpoint-every N` | Remote state flush interval (see below; default 25). |

## Webhook notifications

Downstream services (BuddyPress, Works) cache membership data and must
be told to re-fetch when it changes. The command calls
`ExternalSync.notify_subscribers` once per profile **whose memberships
actually changed** — unchanged profiles generate no traffic. Suppress
entirely with `--no-notify` (for example when rehearsing a run against
a database copy).

## Resuming an interrupted run

A full backfill over a large member base can take hours. With
`--state-file`, every successfully processed username is recorded, and
a re-run with the same state location skips recorded usernames and
continues where the previous run stopped.

- A username is recorded only after its profile is **fully handled**
  (synced and, where applicable, notified), so work in flight at the
  moment of a crash is retried.
- Failed profiles are deliberately **not** recorded; they retry on the
  next run.
- `--dry-run` neither reads nor writes progress records.

### Local state file

```bash
uv run ./manage.py backfill_memberships --full --sleep 1 \
    --state-file /var/tmp/backfill_state.txt
```

The file is appended to and flushed after every profile. Suitable when
the command runs on a persistent host.

### Remote state (ephemeral containers)

When the command runs inside an ephemeral container (ECS task,
Kubernetes job), local files die with the container. `--state-file`
also accepts a [smart-open](https://github.com/piskvorky/smart_open)
URI such as `s3://bucket/key`, storing the state outside the
container:

```bash
uv run ./manage.py backfill_memberships --full --sleep 1 \
    --state-file s3://kc-profiles-ops/backfill/state.txt \
    --checkpoint-every 25

# container dies → run the identical command in a fresh container;
# it loads the state object from S3 and resumes
```

Credentials use the standard boto3 chain (task role, instance profile,
or `AWS_*` environment variables). The role needs `s3:GetObject` and
`s3:PutObject` on the state key.

Object stores cannot append, so remote state rewrites the whole object
every `--checkpoint-every` N processed profiles (default 25) and once
more on completion. Consequences:

- A hard kill (OOM, SIGKILL) loses at most N−1 profiles of progress;
  those profiles are simply re-processed on resume. The operation is
  idempotent, so this is safe.
- Lower N for more durability at the cost of one S3 PUT per N
  profiles. `--checkpoint-every 1` writes after every profile, which
  is negligible next to a `--sleep 1` pause.
- A missing or unreadable state object logs a warning and starts
  fresh; it does not abort the run.

The state format is one username per line in both local and remote
modes, so a state file can be inspected — or edited to force specific
profiles to re-process — with ordinary tools.

## Output

The command finishes with a summary:

```
Processed 12041 profile(s): 384 changed, 384 notified, 17959 skipped, 3 error(s)
```

Failures are logged with tracebacks (see the logging guide) and do not
abort the run.

## Troubleshooting

- **A member is missing from a network listing after a local-mode
  run.** Local mode only covers `KNOWN_SOCIETY_MAPPINGS` societies.
  Membership in MLA, MSU, ARLISNA or UP requires `--full` (or any
  event that triggers a normal sync for that user).
- **Run resumed but reprocessed some profiles.** Expected with remote
  state: up to `--checkpoint-every − 1` profiles since the last
  checkpoint are retried.
- **State object never appears in S3.** Check for an exception in the
  command output: state is first written after the
  `--checkpoint-every`-th profile, so very short runs with large N
  only write on completion. Verify the role has `s3:PutObject`.
