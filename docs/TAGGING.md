# Container image tagging

Every successful CI deploy publishes one or more tags to the relevant
ECR repository (`kcprofiles` / `kcprofiles-dev`,
`kcprofiles-traefik` / `kcprofiles-traefik-dev`, and `kcprofiles-monitor`
on `main`). This document describes which tags are pushed when, what
each one means, and how to use them to roll back in an emergency.

## Tags pushed on every deploy

| Tag                       | Mutability | Pushed on   | Purpose                              |
| ------------------------- | ---------- | ----------- | ------------------------------------ |
| `<git_sha>`               | Immutable  | main, dev   | Exact commit identity (40-char SHA). |
| `v<version>-<sha7>`       | Immutable  | main, dev   | Human-readable, version-anchored, unique per build. **Use this for rollback names.** |
| `v<version>`              | Mutable    | main only   | Pointer to the latest build of a given release. |
| `latest`                  | Mutable    | main, dev   | Pointer to the most recent build on the branch. |

`<version>` is read from the `[project]` table of `pyproject.toml` at
build time. `<sha7>` is the first 7 characters of the commit SHA.

## Why the `-<sha7>` suffix?

Disambiguation. On `dev`, commitizen never bumps the version (the
`Bump version` workflow only runs on pushes to `main`), so every dev
deploy would otherwise compete for the same `v<version>` tag and the
previous build would be untaggable by name. Appending the short SHA
gives every build its own immutable, version-anchored handle.

On `main` the same suffix is still pushed for two reasons:

1. Between a feature merge and the commitizen bump that follows, two
   commits can deploy with the same `v<version>` value, so the suffix
   keeps each build addressable.
2. Symmetry: rollback procedures are the same on both environments.

## Why `v<version>` is `main`-only

`main` runs commitizen on every push and guarantees a fresh version per
release, so `v<version>` is a stable name for "the build that
corresponds to release X.Y.Z." On `dev` the same tag would change
meaning every push, which is misleading — so we don't publish it there.

## Example

For commit `1cd0a566` deployed on `dev` while `pyproject.toml` has
`version = "4.36.1"`, the dev ECR repository receives:

- `kcprofiles-dev:1cd0a566fa...`  (full SHA)
- `kcprofiles-dev:v4.36.1-1cd0a56`
- `kcprofiles-dev:latest`

The same commit, if it were on `main`, would additionally produce:

- `kcprofiles:v4.36.1`

## Rolling back

In an emergency, prefer the immutable, named tag:

```bash
aws ecs update-service \
  --cluster kcprofiles \
  --service kcprofiles-blue \
  --task-definition $(aws ecs register-task-definition \
    --family kcprofiles \
    --container-definitions '[{"name":"django","image":"<account>.dkr.ecr.us-east-1.amazonaws.com/kcprofiles:v4.36.1-1cd0a56", ...}]' \
    --query 'taskDefinition.taskDefinitionArn' --output text) \
  --force-new-deployment
```

In practice this is done by editing the task definition in the AWS
console to point at the desired `v<version>-<sha7>` tag and then
forcing a new deployment.

If you only need to roll the current release back to its previous build
on `main`, the plain `v<version>` tag is the simplest shorthand, but
remember it tracks the **latest** build of that version — once a newer
build is published it moves forward.

## Where the tagging is configured

`.github/workflows/ci.yml`, in the `deploy` job. The `Extract project
version` step reads `pyproject.toml` via `tomllib`; subsequent build
and push steps consume `steps.project_version.outputs.version`
(`v<version>`) and `.build` (`v<version>-<sha7>`).
