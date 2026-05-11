# ruff: noqa: F401, F403, F405, E501
"""Settings module for stress / load testing.

Inherits from `base.py` directly (not `production.py`) so a load-test run
does not require S3 credentials, SparkPost API keys, Sentry, collectfasta,
or any of the other production-only configuration. Only what's actually
exercised by the IDMS login flow under load is configured here.

Activate with:
  DJANGO_SETTINGS_MODULE=config.settings.loadtest
  LOADTEST=1
  CILOGON_DISCOVERY_URL=http://<mock-host>:8080/.well-known/openid-configuration

Required env (no defaults):
  DJANGO_SECRET_KEY            — any non-empty string is fine for load tests
  DATABASE_URL                 — same Postgres the test deployment uses

Recommended env:
  REDIS_SERVER                 — Redis URL (default: redis://localhost:6379)
  CILOGON_CLIENT_ID            — anything; mock doesn't validate
  CILOGON_CLIENT_SECRET        — anything; mock doesn't validate
  CILOGON_DISCOVERY_URL        — point at the mock IdP

Optional:
  LOADTEST_PROMETHEUS=1        — enable django-prometheus /metrics
  LOADTEST_STUB_EXTERNAL_SYNC  — default 1; stubs Mailchimp/MLA/ARLISNA/UP/ROR
  LOADTEST_STUB_IDMS_API       — default 1; stubs the rest_api IDMS event client
  SENTRY_DSN                   — if set, Sentry is initialised; otherwise skipped
"""

import logging
import os
import socket

# `base.py` has a handful of `env(...)` calls with no defaults that would
# otherwise abort import (WEBHOOK_TOKEN, MAILCHIMP_*). Load tests neither
# fire the webhook nor talk to Mailchimp (the loadtest_app stubs ExternalSync),
# so we plant harmless sentinels first and let real env values (when set,
# e.g. on the test deployment) win because setdefault is a no-op then.
for _key, _default in (
    ("WEBHOOK_TOKEN", "loadtest-disabled"),
    ("MAILCHIMP_LIST_ID", "loadtest-disabled"),
    ("MAILCHIMP_API_KEY", "loadtest-disabled"),
    ("MAILCHIMP_DC", "loadtest-disabled"),
    ("MAILCHIMP_NEWSLETTER_GROUP_ID", "loadtest-disabled"),
):
    os.environ.setdefault(_key, _default)

from .base import *  # noqa: E402
from .base import INSTALLED_APPS  # noqa: E402
from .base import MIDDLEWARE  # noqa: E402
from .base import env  # noqa: E402

# --- Safety guard: never load on production by accident -----------------

_BLOCKED_HOSTNAMES = {"profile.hcommons.org", "profile.kcommons.org"}
_hostname = (
    env("LOADTEST_HOSTNAME_OVERRIDE", default="") or socket.getfqdn()
).lower()

if (
    _hostname in _BLOCKED_HOSTNAMES
    and env("LOADTEST_ALLOW_PRODUCTION_HOSTNAME", default="0") != "1"
):
    msg = (
        f"Refusing to load loadtest settings on production hostname "
        f"'{_hostname}'. Set LOADTEST_ALLOW_PRODUCTION_HOSTNAME=1 to override "
        "(do not do this)."
    )
    raise RuntimeError(msg)

# --- Core ---------------------------------------------------------------

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", default="loadtest-not-a-real-secret")

# Match production.py: accept any Host header. The deployment sits behind
# an ALB and the ECS task's health-check probes come in with the container
# IP and `localhost:5000`, neither of which can be hardcoded ahead of time.
# Reading DJANGO_ALLOWED_HOSTS from env (as an earlier revision did) makes
# operators set it in their .envs file — which then bites them when health
# probes start failing with DisallowedHost. So we hardcode the wildcard
# here just like production does.
ALLOWED_HOSTS = ["*"]

ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://profile.hcommons-test.org",
        "http://localhost",
        "http://localhost:8000",
    ],
)

# --- Cache (Redis is required; the cilogon middleware uses it) ----------

_REDIS_URL = env("REDIS_SERVER", default="redis://localhost:6379")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{_REDIS_URL}/profile_default",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{_REDIS_URL}/profile_select2",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "TIMEOUT": 600,
    },
}

# --- Email: never send real mail under load -----------------------------

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "loadtest@example.invalid"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Storage: keep it local. Loads tests don't write static/media. ------

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# --- Logging: stdout JSON-ish, no prod yaml dependency ------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": env("LOADTEST_LOG_LEVEL", default="INFO"),
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOADTEST_LOG_LEVEL", default="INFO"),
    },
}

# --- Optional Sentry: only if DSN provided ------------------------------

if env("SENTRY_DSN", default=""):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            DjangoIntegration(),
            RedisIntegration(),
        ],
        environment=env("SENTRY_ENVIRONMENT", default="loadtest"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )

# --- Activate loadtest_app for monkey-patching --------------------------

INSTALLED_APPS = [
    *INSTALLED_APPS,
    "knowledge_commons_profiles.loadtest_app.apps.LoadTestAppConfig",
]

# django_extensions and sslserver are convenient when running loadtest mode
# locally (the `local` dep group installs them) but aren't available in the
# `dev`/`production` groups used to build the ECS image. Only add them when
# they can actually be imported, so the same settings module works in both
# environments without forcing extra deps into the production install.
import importlib.util as _importlib_util  # noqa: E402

for _optional_app in ("django_extensions", "sslserver"):
    if _importlib_util.find_spec(_optional_app) is not None:
        INSTALLED_APPS.append(_optional_app)


# --- Optional django-prometheus ----------------------------------------

if env.bool("LOADTEST_PROMETHEUS", default=False):
    if _importlib_util.find_spec("django_prometheus") is None:
        msg = (
            "LOADTEST_PROMETHEUS=1 was set but django-prometheus is not "
            "installed. Add it to the deployment image via "
            "`uv sync --group loadtest` or unset the env var."
        )
        raise RuntimeError(msg)
    INSTALLED_APPS = ["django_prometheus", *INSTALLED_APPS]
    MIDDLEWARE = [
        "django_prometheus.middleware.PrometheusBeforeMiddleware",
        *MIDDLEWARE,
        "django_prometheus.middleware.PrometheusAfterMiddleware",
    ]

# --- Allow loadtest broker return_to domains ----------------------------

ALLOWED_CILOGON_FORWARDING_DOMAINS = [
    *globals().get("ALLOWED_CILOGON_FORWARDING_DOMAINS", []),
    "hcommons-test.org",
]

# Ensure LOADTEST is visible inside the running app
os.environ.setdefault("LOADTEST", "1")
