"""Signal handlers that maintain a Redis index from auth user -> active
session keys, so that `app_logout` can fan out to every session this user
holds without scanning the entire `django_session` table."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django_redis import get_redis_connection
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


# Slack on top of SESSION_COOKIE_AGE so the index outlives any session it
# could be tracking. Django's default for SESSION_COOKIE_AGE is 2 weeks.
_TTL_SLACK_SECONDS = 60


def user_session_key(user_id: int | str) -> str:
    """Redis SET key that holds this user's active session_keys."""
    return f"auth_user_sessions:{user_id}"


def _ttl_seconds() -> int:
    cookie_age = int(getattr(settings, "SESSION_COOKIE_AGE", 1209600))
    return cookie_age + _TTL_SLACK_SECONDS


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Record this session_key against the user's session index."""
    if user is None or not getattr(request, "session", None):
        return
    session_key = request.session.session_key
    if not session_key:
        return
    try:
        redis = get_redis_connection("default")
        key = user_session_key(user.id)
        redis.sadd(key, session_key)
        redis.expire(key, _ttl_seconds())
    except RedisError:
        # Index maintenance is best-effort; never fail a login because Redis
        # is briefly unavailable.
        logger.warning(
            "Failed to record session in auth-user index",
            exc_info=True,
        )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Remove this session_key from the user's session index."""
    if user is None or not getattr(request, "session", None):
        return
    session_key = request.session.session_key
    if not session_key:
        return
    try:
        redis = get_redis_connection("default")
        redis.srem(user_session_key(user.id), session_key)
    except RedisError:
        logger.warning(
            "Failed to remove session from auth-user index",
            exc_info=True,
        )
