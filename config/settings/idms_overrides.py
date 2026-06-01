"""
Shared broker overrides for the IDMS settings modules.

The standalone IDMS broker service runs the same lean, async, broker-only
profile whether it sits in front of production or the dev/staging deployment.
Both IDMS settings modules — ``config.settings.idms`` (production-based) and
``config.settings.idms_dev`` (dev-based) — apply these overrides after
inheriting their parent settings, so the broker configuration is defined once
and cannot drift between environments.
"""

from __future__ import annotations


def apply_idms_overrides(settings: dict) -> None:
    """Turn an inherited settings namespace into the IDMS broker profile.

    Mutates ``settings`` (pass ``globals()`` from the calling settings module)
    in place: a broker-only URLconf, a slim async-capable middleware stack, no
    request-level transactions, and a bounded psycopg connection pool.
    """
    # URLs / ASGI: serve only the broker endpoints, under ASGI.
    settings["ROOT_URLCONF"] = "config.broker_urls"
    settings["ASGI_APPLICATION"] = "config.asgi.application"
    settings["WSGI_APPLICATION"] = None

    # silent_login needs the session (oidc_userinfo) and auth (request.user);
    # verify_broker_nonce is bearer-authenticated and csrf-exempt. The main
    # app's custom middlewares (token refresh, garbage collection, referer-nav)
    # all explicitly skip the broker paths, so they are dropped here — keeping
    # the hot path free of sync/async adapter hops.
    settings["MIDDLEWARE"] = [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
    ]

    env = settings["env"]
    databases = settings["DATABASES"]
    # The broker does a single indexed read plus a cache write; it needs no
    # request-level transaction, and wrapping every anonymous redirect in one
    # would pointlessly hold a connection under the redirect storm.
    databases["default"]["ATOMIC_REQUESTS"] = False
    # A bounded pool caps this service's Postgres footprint regardless of how
    # many concurrent redirects are in flight. psycopg's pool requires
    # CONN_MAX_AGE = 0.
    databases["default"]["CONN_MAX_AGE"] = 0
    databases["default"].setdefault("OPTIONS", {})
    databases["default"]["OPTIONS"]["pool"] = {
        "min_size": env.int("IDMS_DB_POOL_MIN", default=2),
        "max_size": env.int("IDMS_DB_POOL_MAX", default=10),
        "timeout": env.int("IDMS_DB_POOL_TIMEOUT", default=10),
    }
