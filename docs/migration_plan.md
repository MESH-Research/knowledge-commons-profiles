# WordPress to Knowledge Commons Profiles Migration Plan

## Context

The Knowledge Commons is transitioning its identity management and profile system from WordPress/BuddyPress (hosted at hcommons.org with MariaDB on AWS) to a new Django-based IDMS and profile system (hosted at profile.hcommons.org with PostgreSQL). The existing `import_from_sql`, `import_profile_images`, `import_cover_images`, and `import_comanage` management commands already handle the data transformation. This plan covers the operational procedure to execute the migration safely with minimal downtime, including simulation, backups, rollback points, and post-migration verification.

**Key constraints**: MySQL dump on the live database crashes the site; the site must be down during migration; CoManage roles must be synced during the same window; the `wordpress-cilogon` branch must be deployed to WordPress; Nginx must redirect old member paths.

---

## Phase 0: Pre-Migration Preparation (2-4 weeks before)

### 0.1 Access and Infrastructure Checklist

Verify all of these before proceeding:

- [ ] SSH access to WordPress production server
- [ ] AWS console access to create/restore RDS snapshots (MariaDB)
- [ ] SSH/Docker access to Django production server
- [ ] COManage Registry API credentials (HTTP Basic Auth)
- [ ] Access to WordPress uploads directory (`/app/uploads/avatars/` and `/app/uploads/buddypress/members/`)
- [ ] Merge/rebase of `wordpress-cilogon` branch with `production` branch
- [ ] Permission to deploy `wordpress-cilogon` branch to WordPress production
- [ ] Permission to modify Nginx configuration for hcommons.org
- [ ] `WORDPRESS_DATABASE_URL` configured in Django production `.envs/.production/.django`

### 0.2 Stand Up a Staging Environment

1. **WordPress staging**: Create an RDS snapshot of production MariaDB, restore to a staging RDS instance
2. **Django staging**: Deploy the profiles app with a separate PostgreSQL instance (use `docker-compose.dev.yml` or a copy of `docker-compose.production.yml`)
3. **Copy uploads**: `rsync` the `/app/uploads/avatars/` and `/app/uploads/buddypress/members/` directories to a staging location

### 0.3 Measure Data Volume

Query staging MariaDB to determine:
- `SELECT COUNT(*) FROM wp_users;`
- `SELECT COUNT(*) FROM wp_bp_xprofile_data;`
- `SELECT COUNT(*) FROM wp_term_relationships;`
- Size of the resulting MySQL dump file

These numbers determine downtime duration. The `import_from_sql` command has an **O(users x xprofile_data_rows)** nested loop (lines 294-317 of `import_from_sql.py`) that may be slow for large datasets. If timing is unacceptable, pre-index `data_values` by `user_id` into a dictionary before the loop.

### 0.4 Known Issue: Image Import WpUser Dependency

Both `import_profile_images` (line 83) and `import_cover_images` (line 67) look up `WpUser.objects.filter(id=user_id)` via the `wordpress_dev` database connection. This means the WordPress MariaDB must be accessible during image import steps, or the commands need modification to use `Profile.objects.filter(central_user_id=user_id)` instead (since `import_from_sql` already populates `central_user_id`).

**Decision needed**: Either keep the WordPress DB accessible during image imports, or patch the commands beforehand.

### 0.5 Known Issue: Image URLs Point to hcommons.org

Both image import commands store absolute URLs pointing to `https://hcommons.org/app/uploads/...`. After migration, Nginx/WordPress must continue serving these static paths, or you need to either:
1. Copy uploads to S3/CDN and update stored URLs
2. Configure Nginx to proxy `/app/uploads/` to the original file store
3. Keep WordPress serving the uploads path (simplest)

### 0.6 Prepare Nginx Redirect Configuration

Draft and test the redirect rules for hcommons.org:

```nginx
# Redirect member profile paths to new profiles system
location ~ ^/members/(.+)$ {
    return 301 https://profile.hcommons.org/members/$1;
}

location = /members/ {
    return 301 https://profile.hcommons.org/members/;
}
```

### 0.7 Prepare wordpress-cilogon Branch

- Rebase `wordpress-cilogon` on current WordPress production branch
- Test against staging WordPress instance
- Document exact deployment steps (git pull, composer install, cache flush, etc.)

### 0.8 Communication

- **2 weeks before**: Email users and add site banner announcing maintenance window
- **1 week before**: Reminder with exact date/time and expected duration
- **Day of**: Display maintenance page

---

## Phase 1: Full Simulation / Dry Run (1-2 weeks before)

Execute the entire migration procedure against staging. Record wall-clock times for every step.

```bash
# 1. Generate MySQL dump from staging MariaDB
mysqldump --single-transaction --quick --lock-tables=false \
  -h <staging-rds-host> -u <user> -p <staging_db_name> \
  wp_users wp_bp_xprofile_fields wp_bp_xprofile_data \
  wp_term_relationships wp_term_taxonomy wp_terms \
  > /path/to/staging-dump.sql

# 2. Run SQL import
docker compose -f docker-compose.dev.yml run --rm django \
  python ./manage.py import_from_sql -file /path/to/staging-dump.sql

# 3. Import profile images
docker compose -f docker-compose.dev.yml run --rm django \
  python ./manage.py import_profile_images /path/to/uploads/buddypress/

# 4. Import cover images
docker compose -f docker-compose.dev.yml run --rm django \
  python ./manage.py import_cover_images /path/to/uploads/buddypress/

# 5. COManage dry run first, then real
docker compose -f docker-compose.dev.yml run --rm django \
  python ./manage.py import_comanage \
    --base-url https://registry.hcommons.org/ \
    --username <api_user> --password <api_pass> --dry-run

docker compose -f docker-compose.dev.yml run --rm django \
  python ./manage.py import_comanage \
    --base-url https://registry.hcommons.org/ \
    --username <api_user> --password <api_pass>
```

### Simulation Validation Checks

Ensure that instances have connectability. Works needs to be able to communicate with the IDMS, the IDMS needs to be able to communicate with Works, and the same with WordPress.

- [ ] IDMS can reach Works
- [ ] IDMS can reach WordPress
- [ ] IDMS can reach Search
- [ ] Works can reach IDMS
- [ ] Works can reach WordPress
- [ ] WordPress can reach IDMS
- [ ] WordPress can reach Works

This routing needs thorough checking as SSO functionality relies upon it.

### Simulation Validation Checks

```bash
docker compose run --rm django python ./manage.py shell -c "
from knowledge_commons_profiles.newprofile.models import *
print(f'Profiles: {Profile.objects.count()}')
print(f'Academic Interests: {AcademicInterest.objects.count()}')
print(f'Profile Images: {ProfileImage.objects.count()}')
print(f'Cover Images: {CoverImage.objects.count()}')
print(f'Persons: {Person.objects.count()}')
print(f'Roles: {Role.objects.count()}')
print(f'Profiles without email: {Profile.objects.filter(email=\"\").count()}')
"
```

Spot-check 10-20 known users: verify name, email, ORCID, about_user, education match the source. Test URL paths return 200. Record total simulation time -- this is your downtime budget (add 50% buffer).

---

## Phase 2: Migration Day Procedure

### 2.1 Pre-flight Checks (T-30 min)

```bash
# Verify Django profiles app is healthy
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/health/

# Verify COManage API is reachable
curl -s -u <user>:<pass> \
  "https://registry.hcommons.org/co_people.json?coid=2&search.identifier=<test_user>"

# Verify disk space on Django server
df -h

# Verify PostgreSQL health
docker compose -f docker-compose.production.yml exec postgres \
  psql -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
```

### 2.2 Enable Maintenance Mode (T=0)

```bash
# On WordPress server:
wp maintenance-mode activate
# Or: serve a static maintenance page via Nginx
```

### 2.3 BACKUP: AWS RDS Snapshot of MariaDB (T+2 min)

> **ROLLBACK POINT A** -- WordPress database can be fully restored from this snapshot

```bash
aws rds create-db-snapshot \
  --db-instance-identifier <wp-rds-instance-id> \
  --db-snapshot-identifier hcommons-pre-migration-$(date +%Y%m%d-%H%M%S)

aws rds wait db-snapshot-available \
  --db-snapshot-identifier hcommons-pre-migration-<timestamp>
```

### 2.4 BACKUP: PostgreSQL Backup (T+15 min)

> **ROLLBACK POINT B** -- Django database can be fully restored from this backup

```bash
docker compose -f docker-compose.production.yml exec postgres backup
# Creates: backup_YYYY_MM_DDTHH_MM_SS.sql.gz in /backups/
# Verify:
docker compose -f docker-compose.production.yml exec postgres backups
```

### 2.5 Generate MySQL Dump (T+20 min)

```bash
# Dump only the 6 tables needed by import_from_sql
# --single-transaction avoids locks (safe since site is in maintenance mode)
mysqldump --single-transaction --quick \
  -h <rds-endpoint> -u <user> -p \
  <db_name> \
  wp_users wp_bp_xprofile_fields wp_bp_xprofile_data \
  wp_term_relationships wp_term_taxonomy wp_terms \
  > /path/to/hcprod.sql
```

### 2.6 Clear Stale Data (T+30 min, if re-running)

Only needed if prior test data exists in the Django database:

```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py shell -c "
from knowledge_commons_profiles.newprofile.models import (
    Profile, AcademicInterest, ProfileImage, CoverImage, Person, Role, CO, COU
)
Role.objects.all().delete()
Person.objects.all().delete()
COU.objects.all().delete()
CO.objects.all().delete()
ProfileImage.objects.all().delete()
CoverImage.objects.all().delete()
Profile.objects.all().delete()
AcademicInterest.objects.all().delete()
print('All profile data cleared')
"
```

### 2.7 Run import_from_sql (T+32 min)

```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py import_from_sql -file /path/to/hcprod.sql
```

Runs inside `@transaction.atomic` -- if it fails midway, no partial data is committed. On failure, simply fix the issue and re-run.

**Checkpoint**:
```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py shell -c "
from knowledge_commons_profiles.newprofile.models import Profile, AcademicInterest
print(f'Profiles: {Profile.objects.count()}')
print(f'Academic Interests: {AcademicInterest.objects.count()}')
"
```

### 2.8 Run import_profile_images (T+varies)

```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py import_profile_images /path/to/uploads/buddypress/
```

**Requires**: `WORDPRESS_DATABASE_URL` pointing to an accessible MariaDB (see 0.4).

### 2.9 Run import_cover_images (T+varies)

```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py import_cover_images /path/to/uploads/buddypress/
```

### 2.10 Run import_comanage (T+varies)

```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py import_comanage \
    --base-url https://registry.hcommons.org/ \
    --username <api_user> --password <api_pass>
```

This is the slowest step -- network-bound with ~3 HTTP requests per user to the COManage API. Has built-in retry logic (5 retries, exponential backoff).

**Note**: If this step is taking too long and all other steps are complete, it can potentially be run after the site goes live since it creates `Person`/`Role` records (not core `Profile` data). Profiles will display without role information until this completes.

**Checkpoint**:
```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py shell -c "
from knowledge_commons_profiles.newprofile.models import Person, Role, CO
print(f'Persons: {Person.objects.count()}')
print(f'Roles: {Role.objects.count()}')
print(f'COs: {CO.objects.count()}')
"
```

### 2.11 Deploy wordpress-cilogon Branch (T+varies)

```bash
# On WordPress production server:
cd /path/to/wordpress
git fetch origin
git checkout wordpress-cilogon
# Run build/install steps as needed
wp cache flush
```

### 2.12 Update Nginx Configuration (T+varies)

Apply the redirect rules drafted in 0.6 on the Nginx server fronting hcommons.org:

```bash
# Edit the Nginx config to add the member path redirects
# Then test and reload:
nginx -t && nginx -s reload
```

### 2.13 Smoke Tests (T+varies)

```bash
# Health check
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/health/

# Profile page loads
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/members/<known_username>/

# Old URL redirects correctly
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}" https://hcommons.org/members/<known_username>/

# Members listing
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/members/

# HTMX endpoints
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/htmx/profile-info/<known_username>/

# REST API
curl -s -o /dev/null -w "%{http_code}" https://profile.hcommons.org/api/v1/members/<known_username>/
```

### 2.14 Disable Maintenance Mode

```bash
wp maintenance-mode deactivate
```

---

## Phase 3: Rollback Procedures

### Before any Django data changes (steps 2.2-2.5)
Simply disable maintenance mode. Nothing has changed.

### After Django imports, before WordPress/Nginx changes (steps 2.7-2.10)
1. Restore PostgreSQL:
   ```bash
   docker compose -f docker-compose.production.yml exec postgres \
     restore backup_YYYY_MM_DDTHH_MM_SS.sql.gz
   ```
2. Disable maintenance mode. Old system is intact.

### After WordPress branch deployment (step 2.11)
1. Revert WordPress: `git checkout <previous-branch>`; `wp cache flush`
2. Restore PostgreSQL from backup
3. Revert Nginx config and reload
4. Disable maintenance mode

### After going live (full rollback)
1. Re-enable maintenance mode
2. Revert Nginx redirects, reload
3. Revert WordPress branch
4. Restore PostgreSQL from backup
5. If needed, restore MariaDB from RDS snapshot
6. Disable maintenance mode

---

## Phase 4: Post-Migration Verification

### Data Integrity
```bash
docker compose -f docker-compose.production.yml run --rm django \
  python ./manage.py shell -c "
from knowledge_commons_profiles.newprofile.models import *
print(f'Profiles: {Profile.objects.count()}')
print(f'Academic Interests: {AcademicInterest.objects.count()}')
print(f'Profile Images: {ProfileImage.objects.count()}')
print(f'Cover Images: {CoverImage.objects.count()}')
print(f'Persons: {Person.objects.count()}')
print(f'Roles: {Role.objects.count()}')
print(f'Profiles without email: {Profile.objects.filter(email=\"\").count()}')
print(f'Profiles linked to Person: {Profile.objects.filter(person_profile__isnull=False).count()}')
print(f'Orphan profile images: {ProfileImage.objects.filter(profile__isnull=True).count()}')
"
```

### URL Matrix
| Old URL | Expected | New URL |
|---------|----------|---------|
| `hcommons.org/members/<user>/` | 301 | `profile.hcommons.org/members/<user>/` |
| `profile.hcommons.org/members/<user>/` | 200 | Profile page renders |
| `profile.hcommons.org/members/` | 200 | Directory listing |
| `profile.hcommons.org/my-profile/` | 302 | Login redirect or own profile |
| `profile.hcommons.org/search/` | 200 | Search page |

### User Acceptance
- 3-5 users log in via CILogon and verify profiles
- Test profile editing (TinyMCE, field saves)
- Test avatar/cover image upload
- Verify HTMX feeds load (Mastodon, Works, blog posts)
- Verify search works

---

## Risk Summary

| Risk | Mitigation |
|------|-----------|
| MySQL dump crashes WordPress | Site in maintenance mode first; dump only 6 tables with `--single-transaction` |
| `import_from_sql` too slow | Pre-measure in simulation; optimize O(N*M) loop if needed |
| `import_from_sql` fails midway | `@transaction.atomic` ensures no partial state; re-run from clean |
| COManage API slow/down | Built-in retry logic; can run post-go-live if needed |
| Image imports can't reach WordPress DB | Keep DB accessible or patch commands to use `central_user_id` (see 0.4) |
| Image URLs break after migration | Keep WordPress serving `/app/uploads/` or set up proxy (see 0.5) |
| Nginx misconfiguration | Test with `nginx -t`; keep old config backed up |
| wordpress-cilogon has issues | Tested on staging; revertible to previous branch |

---

## Estimated Timeline

| Step | Duration | Notes |
|------|----------|-------|
| Maintenance mode | 2 min | |
| RDS snapshot | 10-20 min | AWS wait |
| PostgreSQL backup | 5 min | |
| MySQL dump (6 tables) | 5-15 min | |
| import_from_sql | **Measure in simulation** | Potentially slowest step |
| import_profile_images | 5-15 min | |
| import_cover_images | 5-15 min | |
| import_comanage | **Measure in simulation** | Network-bound, potentially slowest |
| Deploy wordpress-cilogon | 10 min | |
| Nginx reconfiguration | 5 min | |
| Smoke tests | 10 min | |

**Total**: Estimated 2-4 hours. Simulation timing will refine this.

---

## Critical Files

- `newprofile/management/commands/import_from_sql.py` -- SQL import (O(N*M) loop at lines 294-317)
- `newprofile/management/commands/import_comanage.py` -- COManage import
- `newprofile/management/commands/import_profile_images.py` -- WpUser dependency at line 83
- `newprofile/management/commands/import_cover_images.py` -- WpUser dependency at line 67
- `newprofile/wordpress_router.py` -- Routes Wp* models to wordpress_dev DB
- `config/settings/base.py` -- Database configuration
- `compose/production/postgres/maintenance/backup` -- Backup script
- `compose/production/postgres/maintenance/restore` -- Restore script (drops + recreates DB)
