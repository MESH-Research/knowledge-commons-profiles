"""Discover which ECS service this container belongs to.

ECS injects ECS_CONTAINER_METADATA_URI_V4 into every container it runs; the
``/task`` document behind it names the service the task was launched by.
Off ECS (local docker, CI, the host) the variable is absent and we report
nothing rather than guess.
"""

import functools
import logging
import os

import requests

logger = logging.getLogger(__name__)

METADATA_TIMEOUT_SECONDS = 2


@functools.lru_cache(maxsize=1)
def ecs_service_name() -> str | None:
    """Return the ECS service name for this task, or None off ECS.

    Checked in order: the ECS_SERVICE_NAME environment variable, then the
    ECS task metadata endpoint (ECS_CONTAINER_METADATA_URI_V4). The result
    is cached for the life of the process.
    """
    override = os.environ.get("ECS_SERVICE_NAME")
    if override:
        return override

    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not metadata_uri:
        return None

    try:
        response = requests.get(
            f"{metadata_uri}/task", timeout=METADATA_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        service = response.json().get("ServiceName")
    except (requests.exceptions.RequestException, ValueError, AttributeError):
        logger.warning("ECS task metadata unavailable", exc_info=True)
        return None

    return service or None
