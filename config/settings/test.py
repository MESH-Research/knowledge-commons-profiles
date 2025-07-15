"""
With these settings, tests run faster.
"""

import logging.config
from pathlib import Path

import yaml

from .base import *  # noqa: F403
from .base import TEMPLATES
from .base import env

# GENERAL
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="IrCavrCe9sryal1EMPB3lEkv3uQ7uy0cwvjzxyjMLcoCCY7la5MzBEOpsYh4h4uA",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# DEBUGGING FOR TEMPLATES
# -----------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# MEDIA
# -----------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "http://media.testserver/"
# Your stuff...
# -----------------------------------------------------------------------------

with Path("log_config/local.yaml").open(
    "r", errors="ignore", encoding="utf-8"
) as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
