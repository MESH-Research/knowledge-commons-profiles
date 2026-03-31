# healthcheck functions
import logging

import django
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.rest_api.utils import check_api_endpoints_health

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
    except redis.exceptions.ConnectionError:
        logger.exception("Health check: Redis unhealthy")
        health_result["REDIS"] = "unhealthy"
        fail = True
    else:
        health_result["REDIS"] = "healthy"

    try:
        db_conn = connections["wordpress_dev"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError:
        logger.exception("Health check: WordPress DB unhealthy")
        health_result["WordPress DB"] = "unhealthy"
        fail = True
    else:
        health_result["WordPress DB"] = "healthy"

    try:
        db_conn = connections["default"]
        _ = db_conn.cursor()
    except django.db.utils.OperationalError:
        logger.exception("Health check: Postgres DB unhealthy")
        health_result["Postgres DB"] = "unhealthy"
        fail = True
    else:
        health_result["Postgres DB"] = "healthy"

    try:
        api_results = check_api_endpoints_health()
        if api_results:
            health_result["API Endpoints"] = api_results
    except Exception:
        logger.exception("Health check: API endpoint check failed")
        health_result["API Endpoints"] = "check failed"

    health_result["Debug Mode"] = settings.DEBUG

    health_result["VERSION"] = VERSION

    return JsonResponse(health_result, status=200 if not fail else 500)
