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

from .idms_overrides import apply_idms_overrides
from .production import *  # noqa: F403

# Apply the lean broker profile (broker-only URLconf, slim async middleware, no
# ATOMIC_REQUESTS, bounded psycopg pool). Shared with config.settings.idms_dev.
apply_idms_overrides(globals())
