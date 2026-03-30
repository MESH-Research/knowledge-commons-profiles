# CI/Deploy Pipeline Optimization

## Problem

The current CI/CD setup has three workflow files with significant duplication:
- `ci.yml` runs tests and linting on x86
- `deploy.yml` rebuilds images from scratch on ARM and deploys to production
- `deploy-dev.yml` is nearly identical to `deploy.yml` but targets dev

Deploy workflows trigger via `workflow_run` after CI completes, adding delay. Images are built twice: once for testing (x86), once for deployment (ARM).

## Design

Merge all three workflows into a single `ci.yml` running entirely on ARM (`ubuntu-24.04-arm`). The pipeline has three jobs:

### Jobs

**`linter`** (runs on all PRs and pushes to dev/main)
- Runs pre-commit checks
- No changes from current behavior, just runs on ARM

**`test`** (runs on all PRs and pushes to dev/main)
- Builds via `docker-compose.github.yml` (includes Postgres for testing)
- Runs migrations, Django tests, pytest, coverage
- Same steps as current CI, just on ARM

**`deploy`** (runs only on push to dev or main, after test + linter pass)
- Needs: `[linter, test]`
- Condition: `github.event_name == 'push'`
- Configures environment variables based on branch:
  - `dev` branch: dev ECR repos, dev ECS cluster, `docker-compose.dev.yml`
  - `main` branch: prod ECR repos, prod ECS cluster, `docker-compose.production.yml`
- Logs into ECR, builds deployment images, pushes to ECR
- Forces ECS redeployment and autoscaling instance refresh
- Creates Sentry release
- Monitor image is built and pushed only for `main` branch

### Branch-to-environment mapping

| Setting | `dev` | `main` |
|---------|-------|--------|
| Compose file | `docker-compose.dev.yml` | `docker-compose.production.yml` |
| ECR django | `kcprofiles-dev` | `kcprofiles` |
| ECR traefik | `kcprofiles-traefik-dev` | `kcprofiles-traefik` |
| ECR monitor | n/a | `kcprofiles-monitor` |
| ECS cluster | `kcprofiles-dev-2` | `kcprofiles` |
| ECS service | `kcprofiles-dev` | `kcprofiles-blue` |
| Autoscale group | `Infra-ECS-Cluster-kcprofiles-dev-2-f89c2350-ECSAutoScalingGroup-zUYaGlEf1GWi` | `Infra-ECS-Cluster-kcprofiles-ee645084-ECSAutoScalingGroup-v3MrRnH7laIx` |
| GitHub environment | `dev` | `production` |
| Sentry environment | `dev` | `production` |

### Files changed

- **Modified:** `.github/workflows/ci.yml` - unified pipeline
- **Deleted:** `.github/workflows/deploy.yml`, `.github/workflows/deploy-dev.yml`
- **Unchanged:** All Dockerfiles, compose files, AWS scripts, `version-release.yml`

### Why two builds remain

The test job uses `docker-compose.github.yml` because it bundles a Postgres service and test-specific configuration. The deploy job builds the real deployment images from the environment-specific compose file. These are architecturally different images serving different purposes, so the double-build is intentional and correct.

### Improvement over current setup

1. No `workflow_run` delay between CI and deploy
2. One workflow file instead of three
3. Consistent ARM architecture throughout
4. Deploy only runs on push (not PRs), gated by test + lint success
5. Branch-based conditionals replace duplicated files
