"""
Settings for the standalone IDMS broker service (dev/staging deployment).

Same lean, async, broker-only profile as :mod:`config.settings.idms`, but
inheriting :mod:`config.settings.dev` (dev database, cache, hosts and Sentry
config) instead of production.

As on production, IDMS MUST share ``DJANGO_SECRET_KEY``, the session store
(Redis + Postgres) and ``STATIC_API_BEARER`` with the dev deployment's main app
so it can read the same sessions and verify the same broker nonces. Those all
come from the shared dev environment.
"""

from .dev import *  # noqa: F403
from .idms_overrides import apply_idms_overrides

# Apply the lean broker profile shared with config.settings.idms.
apply_idms_overrides(globals())
