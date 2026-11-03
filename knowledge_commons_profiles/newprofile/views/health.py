# healthcheck functions
import logging
import platform

import django
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile.ecs_metadata import ecs_service_name
from knowledge_commons_profiles.rest_api.utils import check_api_endpoints_health
from knowledge_commons_profiles.up_salesforce.checks import sync_status

logger = logging.getLogger(__name__)

REDIS_TEST_TIMEOUT_VALUE = 25


def _add_sync_status(request, health_result):
    """
    Add per-sync-class credential status for superusers only. The status
    reveals deployment configuration, so anonymous callers (load-balancer
    probes carry no user at all) and ordinary users never see the key.
    """
    user = getattr(request, "user", None)
    if not (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
    ):
        return
    try:
        health_result["sync"] = sync_status()
    except Exception:
        logger.exception("Health check: sync status check failed")
        health_result["sync"] = "check failed"


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
    health_result["Branch"] = settings.APP_BRANCH
    health_result["Image"] = settings.BUILD_TAG
    health_result["SHA"] = settings.GIT_SHA
    health_result["Python"] = platform.python_version()
    health_result["ECS Service"] = ecs_service_name() or "unavailable"

    _add_sync_status(request, health_result)

    return JsonResponse(health_result, status=200 if not fail else 500)
