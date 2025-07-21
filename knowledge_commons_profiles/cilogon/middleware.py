"""
Middleware for profiles
"""

import contextlib
import logging
from datetime import timedelta

import requests
import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.core.cache import cache
from django.core.exceptions import FieldError
from django.db import DatabaseError
from django.db import OperationalError
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models.enums import IntEnum
from django.http import HttpRequest
from django.urls import resolve
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.cilogon.oauth import delete_associations
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.cilogon.oauth import token_expired
from knowledge_commons_profiles.cilogon.views import revoke_token

logger = logging.getLogger(__name__)

User = get_user_model()


def should_run_middleware(
    request: HttpRequest, key: str, interval: int = 10
) -> bool:
    # if this is the health endpoint, identified by name "healthcheck" in
    # urls/request, return false
    if resolve(request.path_info).url_name == "healthcheck":
        # this ensures that we don't touch the REDIS cache on the healthcheck
        # as it can be down
        return False

    now = timezone.now()

    cache_key = f"{key}-{request.user.id if request.user.is_authenticated
    else request.META.get('REMOTE_ADDR')}"

    last_run = cache.get(cache_key)

    if not last_run or now - last_run >= timedelta(seconds=interval):
        cache.set(cache_key, now, timeout=interval + 5)
        return True

    return False


class RefreshBehavior(IntEnum):
    CLEAR = 0
    IGNORE = 1


class AutoRefreshTokenMiddleware(MiddlewareMixin):
    """
    Middleware to refresh tokens
    """

    def process_request(self, request):
        if not should_run_middleware(request, "auto-refresh"):
            return

        # Grab the stored token
        token = request.session.get("oidc_token")
        if not token:
            # could be during login cycle
            return

        # determine whether we have a user
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            # user is not logged in
            return

        # get the user's browser user-agent
        user_agent = request.headers.get("user-agent", "")

        # store the user's browser user-agent, token, and app
        _, created = TokenUserAgentAssociations.objects.get_or_create(
            user_agent=user_agent,
            app="Profiles",
            refresh_token=token["refresh_token"],
            access_token=token["access_token"],
            user_name=user.username,
        )

        if created:
            logger.debug(
                "Storing token for user %s and user agent %s on app Profiles",
                user,
                user_agent,
            )

        # first, do hard refresh override
        # this is a flag set by the logout routine to force a hard
        # refresh on the next page load, because the user is logged out
        hard_refresh = request.session.get("hard_refresh", False)

        if hard_refresh:
            # send a refresh request
            self.refresh_user_token(
                request, token, user, refresh_behavior=RefreshBehavior.CLEAR
            )
            return

        # determine whether token is expired
        if not token_expired(token, user):
            # token is still valid
            logger.debug(
                "Token is still valid, not refreshing for user %s "
                "and user agent %s",
                user,
                user_agent,
            )
            return

        self.refresh_user_token(request, token)

    def acquire_refresh_lock(self, user_id, timeout=10):
        """
        Attempt to acquire a refresh lock
        """
        return cache.add(
            key=f"refresh-lock:{user_id}", value=True, timeout=timeout
        )

    def release_refresh_lock(self, user_id):
        """
        Release a refresh lock
        """
        cache.delete(f"refresh-lock:{user_id}")

    def refresh_user_token(
        self,
        request,
        token,
        user: User = None,
        refresh_behavior: RefreshBehavior = RefreshBehavior.IGNORE,
    ):
        """
        Refresh and store the new token
        """
        try:
            logger.debug("Refreshing login token for user %s", user)

            cache_key = user.id if user else request.META.get("REMOTE_ADDR")

            if self.acquire_refresh_lock(cache_key):
                try:
                    refresh_token = token.get("refresh_token")

                    if not refresh_token:
                        logger.warning(
                            "Cannot refresh token for %s: no "
                            "refresh_token present in session token",
                            user,
                        )
                        logout(request)
                        return

                    new_token = oauth.cilogon.fetch_access_token(
                        refresh_token=refresh_token,
                        grant_type="refresh_token",
                    )

                    if "access_token" not in new_token:
                        logger.warning(
                            "Refreshed token for %s missing access_token",
                            user,
                        )
                        logout(request)
                        return

                    store_session_variables(request, new_token)
                finally:
                    self.release_refresh_lock(cache_key)
            else:
                logger.debug(
                    "Token refresh lock in place for user %s; skipping",
                    user,
                )

        except OAuthError:
            # user has an invalid refresh token
            # has been revoked centrally at CILogon
            logger.debug("Login token for user %s expired. Logging out.", user)

            with contextlib.suppress(KeyError):
                del request.session["oidc_token"]
                del request.session["oidc_userinfo"]

            logout(request)
        except Exception:  # noqa: BLE001
            logger.warning("Unable to hard refresh token for unknown reason")

            with contextlib.suppress(KeyError):
                del request.session["oidc_token"]
                del request.session["oidc_userinfo"]
        else:
            if refresh_behavior == RefreshBehavior.CLEAR:
                request.session["hard_refresh"] = False


class GarbageCollectionMiddleware(MiddlewareMixin):
    """
    Middleware to clear out token database
    """

    def process_request(self, request):
        if not should_run_middleware(request, "garbage"):
            return

        # Grab the stored token
        token = request.session.get("oidc_token")
        if not token:
            # if there's no token, then do nothing as we can't do any
            # revocation
            return

        # get all TokenUserAgentAssociations with either a blank/null
        # creation date or a creation date that was created at least
        # settings.CILOGON_TOKEN_CLEAROUT_DAYS days ago from now
        associations = self.garner_associations()

        # do nothing if we have nothing to do
        count = associations.count()

        if count == 0:
            logger.info("Garbage collection found nothing to clean")
            return

        # set up a client
        client = oauth.cilogon
        client.load_server_metadata()
        revocation_endpoint = client.server_metadata.get("revocation_endpoint")

        if not revocation_endpoint:
            logger.warning(
                "CILogon revocation endpoint not found in metadata; skipping GC"
            )
            return

        logger.info("Garbage collecting %s tokens", count)

        self.revoke_token_set(associations, client, revocation_endpoint, token)

        delete_associations(associations)

    def revoke_token_set(
        self,
        associations: QuerySet[TokenUserAgentAssociations],
        client,
        revocation_endpoint: str,
        token,
    ):
        """
        Revoke tokens
        """
        for association in associations:
            logger.debug(
                "Revoking token for user %s and user agent %s on app Profiles",
                association.user_name,
                association.user_agent,
            )

            try:
                # revoke both refresh and access tokens
                revoke_token(
                    client=client,
                    revocation_url=revocation_endpoint,
                    token_with_privilege=token,
                    token_revoke={
                        "refresh_token": association.refresh_token,
                        "access_token": association.access_token,
                    },
                )

            except (
                TypeError,
                KeyError,
                ValueError,
                OAuthError,
                requests.RequestException,
            ):
                logger.warning(
                    "Unable to revoke token %s",
                    association,
                )

    def garner_associations(self):
        """
        Get all TokenUserAgentAssociations with either a blank/null date
        or a creation date that was created at least
        settings.CILOGON_TOKEN_CLEAROUT_DAYS days ago from now
        """
        time_cutoff = timezone.now() - timedelta(
            days=settings.CILOGON_TOKEN_CLEAROUT_DAYS
        )

        try:
            return TokenUserAgentAssociations.objects.filter(
                Q(created_at__isnull=True) | Q(created_at__lte=time_cutoff)
            )
        except FieldError:
            logger.exception(
                "Unable to fetch tokens for user agents during garbage "
                "collection due to field error"
            )
            sentry_sdk.capture_exception()
        except DatabaseError:
            logger.exception(
                "Unable to fetch tokens for user agents during garbage "
                "collection due to database error"
            )
            sentry_sdk.capture_exception()
        except OperationalError:
            logger.exception(
                "Unable to fetch tokens for user agents during garbage "
                "collection due to database operational error"
            )
            sentry_sdk.capture_exception()
        except Exception:
            logger.exception(
                "Unable to fetch tokens for user agents during garbage "
                "collection due to other error"
            )
            sentry_sdk.capture_exception()

        return TokenUserAgentAssociations.objects.none()
