"""
Views for CILogon

"""

import logging

import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import forward_url
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import pack_state
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.newprofile.api import User

logger = logging.getLogger(__name__)


def cilogon_login(request):
    """
    The login redirect for OAuth
    :param request: the request
    """

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
            request, prompt="none", claims_cls=ORCIDHandledToken
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
        sub=userinfo["sub"]
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
    return None


def find_user_and_login(request, sub_association):
    """
    Find the user and log them in
    """
    # does the user exist in Django?
    user = User.objects.filter(
        username=sub_association.profile.username
    ).first()

    if user:
        logger.info(
            "Logging in user %s from sub %s",
            user.username,
            sub_association.sub,
        )
    else:
        # there is no user at the moment, so create one
        # note: this is an odd situation as the user has a Profile
        # but not a User
        user = User.objects.create(
            username=sub_association.profile.username,
            email=sub_association.profile.email,
        )

    # log the user in
    login(request, user)


def logout(request):
    # 1. Pull off the ID Token so we can hint it to CILogon
    id_token = request.session.get("oidc_token", {}).get("id_token")

    # 2. Find the OP's end_session_endpoint in the metadata
    client = oauth.create_client("cilogon")
    end_session = client.server_metadata.get("end_session_endpoint")

    # 3. Kill the local Django session immediately
    # TODO: kill session

    # you might also want to: request.session.flush()

    # 4. If the OP supports RP-Initiated Logout, send them there;
    #    otherwise just go back to your site's post-logout page.
    if end_session and id_token:
        redirect_url = settings.LOGOUT_REDIRECT_URL  # e.g. "/"
        return redirect(
            f"{end_session}"
            f"?id_token_hint={id_token}"
            f"&post_logout_redirect_uri={redirect_url}"
        )

    return redirect(settings.LOGOUT_REDIRECT_URL)
