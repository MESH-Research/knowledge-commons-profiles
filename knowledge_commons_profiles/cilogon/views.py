"""
Views for CILogon

"""

import logging
from enum import IntEnum

import requests
import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import delete_associations
from knowledge_commons_profiles.cilogon.oauth import find_user_and_login
from knowledge_commons_profiles.cilogon.oauth import forward_url
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import pack_state
from knowledge_commons_profiles.cilogon.oauth import revoke_token
from knowledge_commons_profiles.cilogon.oauth import store_session_variables

logger = logging.getLogger(__name__)


class RedirectBehaviour(IntEnum):
    """
    Enum for redirect behaviour
    """

    REDIRECT = 1
    NO_REDIRECT = 2


def cilogon_login(request):
    """
    The login redirect for OAuth
    :param request: the request
    """
    # flush the session
    app_logout(request, redirect_behaviour=RedirectBehaviour.NO_REDIRECT)
    request.session.flush()

    # can use this to pass a next_url if we wish
    # an empty string assumes authentication to Profiles app
    # values for base domain here must be present in
    # settings.ALLOWED_CILOGON_FORWARDING_DOMAINS
    state = pack_state("")

    redirect_uri = request.build_absolute_uri("/" + settings.OIDC_CALLBACK)

    return oauth.cilogon.authorize_redirect(request, redirect_uri, state=state)


def callback(request):
    """
    The callback view for OAuth
    :param request: request
    """

    # forward the code to the next URL if it's valid
    forwarding_url = forward_url(request)
    if forwarding_url:
        return forwarding_url

    # no "next" was found or was valid, so we will decode the result here
    try:
        token = oauth.cilogon.authorize_access_token(
            request, claims_cls=ORCIDHandledToken
        )
    except OAuthError as e:
        # send to Sentry if there are errors that are not just the user
        # not being found etc.
        if "Client has not been approved. Unapproved client" in e.description:
            sentry_sdk.capture_exception(e)

        return render(
            request=request,
            template_name="newprofile/auth_error.html",
            context={"exception": e},
        )

    userinfo = store_session_variables(request, token)

    # our linking logic:
    # see whether we have a sub object
    sub_association = SubAssociation.objects.filter(
        sub=userinfo.get("sub", "")
    ).first()

    # do we have a sub->profile?
    if sub_association:
        # yes, found a sub->profile, log them in
        find_user_and_login(request, sub_association)

        # update user network affiliations
        # TODO: update user network affiliations

        # return to the profile page
        return redirect(reverse("my_profile"))

    # no, no user. Redirect to the profile association page
    # TODO: redirect to the profile association page
    return None


def app_logout(
    request,
    redirect_behaviour: RedirectBehaviour = RedirectBehaviour.REDIRECT,
    user_name=None,
    user_agent=None,
    apps=None,
):
    """
    Log the user out of all sessions sharing this user agent
    """

    if not apps:
        apps = settings.CILOGON_APP_LIST

    # An important note: CILogon does not support the end_session_endpoint
    # hence we have to revoke keys manually to do full federated logout

    # 1. Pull off the ID Token so we can hint it to CILogon
    token = request.session.get("oidc_token", {})

    # 2. Find the OP's end_session_endpoint in the metadata
    client = oauth.create_client("cilogon")
    client.load_server_metadata()
    revocation_endpoint = client.server_metadata.get("revocation_endpoint")

    # set flag to middleware
    request.session["hard_refresh"] = True
    request.session.save()

    # get current username
    user_name = user_name if user_name else request.user.username

    user_agent = (
        user_agent if user_agent else request.headers.get("user-agent", "")
    )

    # get all token associations for this browser
    token_associations = TokenUserAgentAssociations.objects.filter(
        user_agent=user_agent,
        app__in=apps,
        user_name=user_name,
    )

    if token_associations.exists():
        # for each relevant token, revoke on CILogon
        for token_association in token_associations:
            # for each relevant token, revoke on CILogon, with this token
            # last
            try:
                revoke_token(
                    client=client,
                    revocation_url=revocation_endpoint,
                    token_with_privilege=token,
                    token_revoke={
                        "refresh_token": token_association.refresh_token,
                        "access_token": token_association.access_token,
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
                    token_association,
                )

            # delete these token associations that have now been revoked
            delete_associations(token_associations)

        # now revoke our token, in case it wasn't in the list
        try:
            revoke_token(
                client=client,
                revocation_url=revocation_endpoint,
                token_with_privilege=token,
                token_revoke={
                    "refresh_token": token.get("refresh_token", ""),
                    "access_token": token.get("access_token", ""),
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
                token,
            )

    # Kill the local Django session immediately
    logout(request)

    if redirect_behaviour == RedirectBehaviour.REDIRECT:
        # redirect the user to the home page
        # TODO: proper redirect
        return redirect("/")

    return None
