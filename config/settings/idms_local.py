"""
Settings for running the IDMS broker locally (developer machines, smoke tests).

Same lean broker profile as :mod:`config.settings.idms`, but inheriting
:mod:`config.settings.local` — so it loads with the local defaults (``DEBUG``,
the local ``SECRET_KEY`` fallback) and points at whatever ``DATABASE_URL`` /
``REDIS_SERVER`` your local ``.env`` provides.

Boot the broker locally with::

    DJANGO_READ_DOT_ENV_FILE=True \\
    DJANGO_SETTINGS_MODULE=config.settings.idms_local \\
        uv run uvicorn config.asgi:application --port 8000

The anonymous silent-login path needs no database or cache; ``/broker/health/``,
the authenticated path and ``/broker/verify-nonce/`` additionally need a
reachable Redis and Postgres.
"""

from .idms_overrides import apply_idms_overrides
from .local import *  # noqa: F403

# Apply the lean broker profile shared with config.settings.idms.
apply_idms_overrides(globals())
