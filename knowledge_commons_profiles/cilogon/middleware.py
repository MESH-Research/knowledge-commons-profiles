"""
Middleware for profiles
"""

import json
import logging

from authlib.integrations.base_client import OAuthError
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin

from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.cilogon.oauth import token_expired

logger = logging.getLogger(__name__)

User = get_user_model()


class AutoRefreshTokenMiddleware(MiddlewareMixin):
    """
    Middleware to refresh tokens
    """

    def process_request(self, request):
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
        logger.debug(
            "Storing token for user %s and user agent %s on app Profiles",
            user,
            user_agent,
        )
        TokenUserAgentAssociations.objects.update_or_create(
            user_agent=user_agent,
            app="Profiles",
            defaults={"token": json.dumps(token)},
        )

        # first, do hard refresh override
        # this is a flag set by the logout routine to force a hard
        # refresh on the next page load, because the user is logged out
        hard_refresh = request.session.get("hard_refresh", False)

        if hard_refresh:
            try:
                logger.debug("Hard refreshing login token for user %s", user)

                # send a refresh request
                new_token = oauth.cilogon.fetch_access_token(
                    refresh_token=token["refresh_token"],
                    grant_type="refresh_token",
                )
                store_session_variables(request, new_token)
            except OAuthError:
                # user has an invalid refresh token
                # has been revoked centrally at CILogon
                logger.debug(
                    "Login token for user %s expired. Logging out.", user
                )
                logout(request)

            request.session["hard_refresh"] = False
            return

        # determine whether token is expired
        if not token_expired(token, user):
            # token is still valid
            return

        try:
            logger.debug("Refreshing login token for user %s", user)

            # refresh the token
            new_token = oauth.cilogon.fetch_access_token(
                refresh_token=token["refresh_token"],
                grant_type="refresh_token",
            )
            store_session_variables(request, new_token)

        except OAuthError:
            # refresh token has expired
            logger.debug("Login token for user %s expired. Logging out.", user)
            logout(request)
