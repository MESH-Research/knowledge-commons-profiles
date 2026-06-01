"""
Settings for the standalone IDMS broker service.

Inherits :mod:`config.settings.production` — it needs the real ``CACHES``,
``SECRET_KEY``, Sentry, security/proxy settings and the shared database — and
overrides only what makes this a lean, asynchronous, broker-only service:

* a minimal URLconf exposing only the broker endpoints (``config.broker_urls``);
* a slim, fully async-capable middleware stack (the broker only needs sessions
  and auth to read ``request.user`` / ``oidc_userinfo``);
* no ``ATOMIC_REQUESTS``, so the anonymous silent-login redirect storm does not
  hold a database connection per request; and
* a bounded psycopg connection pool, so this service cannot exhaust Postgres
  connections under load.

It MUST share ``DJANGO_SECRET_KEY``, the session store (Redis + Postgres) and
``STATIC_API_BEARER`` with the main app so it can read the same sessions and
verify the same broker nonces. Those all come from the shared environment.
"""

from .production import *  # noqa: F403
from .production import DATABASES
from .production import env

# URLs / ASGI
# -----------------------------------------------------------------------------
ROOT_URLCONF = "config.broker_urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = None

# Middleware
# -----------------------------------------------------------------------------
# silent_login needs the session (oidc_userinfo) and auth (request.user);
# verify_broker_nonce is bearer-authenticated and csrf-exempt. The main app's
# custom middlewares (token refresh, garbage collection, referer-nav) all
# explicitly skip the broker paths, so they are dropped here — keeping the hot
# path free of sync/async adapter hops.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

# Database
# -----------------------------------------------------------------------------
# The broker does a single indexed read plus a cache write; it needs no
# request-level transaction, and wrapping every anonymous redirect in one would
# pointlessly hold a connection under the redirect storm.
DATABASES["default"]["ATOMIC_REQUESTS"] = False
# A bounded pool caps this service's Postgres footprint regardless of how many
# concurrent redirects are in flight. psycopg's pool requires CONN_MAX_AGE = 0.
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["pool"] = {
    "min_size": env.int("IDMS_DB_POOL_MIN", default=2),
    "max_size": env.int("IDMS_DB_POOL_MAX", default=10),
    "timeout": env.int("IDMS_DB_POOL_TIMEOUT", default=10),
}
