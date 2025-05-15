"""
Views for CILogon

"""

import binascii
import contextlib
import json
import logging
import urllib.parse as urlparse

import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.shortcuts import redirect
from django.shortcuts import render

from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import extract_code_next_url
from knowledge_commons_profiles.cilogon.oauth import generate_next_url
from knowledge_commons_profiles.cilogon.oauth import oauth

logger = logging.getLogger(__name__)


def login(request):
    """
    The login redirect for OAuth
    :param request: the request
    """

    redirect_uri = request.build_absolute_uri("/" + settings.OIDC_CALLBACK)
    return oauth.cilogon.authorize_redirect(request, redirect_uri)


def callback(request):
    """
    The callback view for OAuth
    :param request: request
    """

    # attempt to decode state to see if there is a next URL
    # if there is, we want to forward the code to the next URL for it to decode
    # If there is no next URL, we want to decode the code here and login
    with contextlib.suppress(
        json.JSONDecodeError, TypeError, binascii.Error, ValueError
    ):
        code, next_url = extract_code_next_url(request)

        if next_url:
            url_parts = generate_next_url(code, next_url, request)

            return redirect(str(urlparse.urlunparse(url_parts)))

    # no "next" was found, so we will decode the result here
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

    userinfo = token["userinfo"]
    request.session["oidc_token"] = token
    request.session["oidc_userinfo"] = userinfo

    # our linking logic:
    logger.info("Token %s", token)
    logger.info("Linking user %s", userinfo)

    # determine whether we have an account here

    if next_url:
        return redirect(next_url)

    return None


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
