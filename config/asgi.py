"""
ASGI config for knowledge-commons-profiles.

Exposes the module-level ``application`` used by ASGI servers (uvicorn). This is
the entrypoint for the standalone IDMS broker container, which runs::

    uvicorn config.asgi:application

with ``DJANGO_SETTINGS_MODULE=config.settings.idms``. The default below mirrors
``config.wsgi`` so the module is importable without that override too.
"""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

# This allows easy placement of apps within the interior
# knowledge_commons_profiles directory.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(str(BASE_DIR / "knowledge_commons_profiles"))
# Defer to a DJANGO_SETTINGS_MODULE already in the environment; the IDMS start
# script sets it to config.settings.idms.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# This application object is used by any ASGI server configured to use this
# file.
application = get_asgi_application()
