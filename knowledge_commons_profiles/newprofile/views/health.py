# healthcheck functions
import logging

import django
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse

from knowledge_commons_profiles.__version__ import VERSION

logger = logging.getLogger(__name__)

REDIS_TEST_TIMEOUT_VALUE = 25


def health(request):
    """
    Healthcheck URL
    """
    health_result = {}
    fail = False

    try:
        cache.set("health", "healthy", REDIS_TEST_TIMEOUT_VALUE)
        _ = cache.get("health")
    except redis.exceptions.ConnectionError as ce:
        health_result["REDIS"] = f"unhealthy: {ce}"
        fail = True
    else:
        health_result["REDIS"] = "healthy"

    try:
        # Test WordPress database connection
        db_conn = connections["wordpress_dev"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError as oe:
        health_result["WordPress DB"] = f"unhealthy: {oe}"
        fail = True
    else:
        health_result["WordPress DB"] = "healthy"

    try:
        # Test Postgres database connection
        db_conn = connections["default"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError as oe:
        health_result["Postgres DB"] = f"unhealthy: {oe}"
        fail = True
    else:
        health_result["Postgres DB"] = "healthy"

    health_result["Debug Mode"] = settings.DEBUG

    health_result["VERSION"] = VERSION

    return JsonResponse(health_result, status=200 if not fail else 500)
