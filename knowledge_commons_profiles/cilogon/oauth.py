"""OAuth initializer"""

import base64
import binascii
import contextlib
import json
import logging
import time
import urllib.parse as urlparse
from urllib.parse import urlencode

import sentry_sdk
import tldextract
from authlib.integrations.django_client import OAuth
from authlib.jose.errors import InvalidClaimError
from authlib.oidc.core import CodeIDToken
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db import IntegrityError
from django.db import OperationalError
from django.db.models import ProtectedError
from django.shortcuts import redirect
from idna import IDNAError

logger = logging.getLogger(__name__)

oauth = OAuth()

oauth.register(
    name="cilogon",
    client_id=settings.CILOGON_CLIENT_ID,
    client_secret=settings.CILOGON_CLIENT_SECRET,
    server_metadata_url=settings.CILOGON_DISCOVERY_URL,
    client_kwargs={"scope": settings.CILOGON_SCOPE},
)


class ORCIDHandledToken(CodeIDToken):
    def validate_amr(self):
        """OPTIONAL. Authentication Methods References. JSON array of strings
        that are identifiers for authentication methods used in the
        authentication. For instance, values might indicate that both password
        and OTP authentication methods were used. The definition of particular
        values to be used in the amr Claim is beyond the scope of this
        specification. Parties using this claim will need to agree upon the
        meanings of the values used, which may be context-specific. The amr
        value is an array of case sensitive strings. However, ORCID sends
        just a string back and this causes a validation error. This patched
        version fixes it.
        """
        amr = self.get("amr")
        if amr and not isinstance(self["amr"], list | str):
            claim_error = "amr"
            raise InvalidClaimError(claim_error)


def generate_next_url(code, next_url, request):
    """
    Generates a URL for forwarding preserving existing querystring parameters
    """
    params = {"code": code, "state": request.GET.get("state")}

    url_parts = list(urlparse.urlparse(next_url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urlencode(query)

    return url_parts


def extract_code_next_url(request):
    """
    Extract the code and next url from the incoming callback request
    """
    b64 = request.GET.get("state")
    data = json.loads(base64.urlsafe_b64decode(b64).decode())

    # see if we have a forwarding URL
    next_url = data.get("next")
    code = request.GET.get("code")

    return code, next_url


def pack_state(next_url):
    """
    B64 encode a next URL
    """
    # Pack next_url into state and b64 encode
    return base64.urlsafe_b64encode(
        json.dumps({"next": next_url}).encode()
    ).decode()


def forward_url(request):
    """
    Forward the code to the next URL (return a redirect) or return None
    """
    # attempt to decode state to see if there is a next URL
    # if there is, we want to forward the code to the next URL for it to decode
    # If there is no next URL, we want to decode the code here and login
    with contextlib.suppress(
        json.JSONDecodeError, TypeError, binascii.Error, ValueError
    ):
        code, next_url = extract_code_next_url(request)

        if next_url and next_url != "":
            url_parts = generate_next_url(code, next_url, request)

            try:
                # parse netloc into subdomain, base domain etc.
                extract_result = tldextract.extract(next_url)

                # validate that the next URL is in the allowed list
                # settings.ALLOWED_CILOGON_FORWARDING_DOMAINS
                if (
                    extract_result.domain + "." + extract_result.suffix
                ) in settings.ALLOWED_CILOGON_FORWARDING_DOMAINS:
                    logger.info("Forwarding CILogon code to %s", next_url)
                    return redirect(str(urlparse.urlunparse(url_parts)))
                logger.warning(
                    "Disallowed CILogon code forwarding URL: %s", next_url
                )
            except (ValueError, IDNAError, UnicodeDecodeError, OSError) as e:
                sentry_sdk.capture_exception(e)
                logger.exception(
                    "Exception parsing and validating next_url: %s", next_url
                )

    return None


def store_session_variables(request, token):
    """
    Store session variables "userinfo" and "oidc_token"
    """
    logger.info("Storing new token")

    request.session["oidc_token"] = token

    userinfo = request.session.get("oidc_userinfo", {})

    if "userinfo" in token:
        userinfo = token["userinfo"]
        request.session["oidc_userinfo"] = userinfo

    return userinfo


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
        user = User.objects.create(
            username=sub_association.profile.username,
            email=sub_association.profile.email,
        )

    # log the user in
    login(request, user)


def token_expired(token, user):
    """
    Check if the token has expired
    """
    now = time.time()
    expires_at = token.get("expires_at", 0)

    # if we're not yet expired, nothing to do
    if (
        expires_at
        and now < expires_at - settings.CILOGON_REFRESH_TOKEN_TIMEOUT
    ):
        logger.debug(
            "Login token for user %s is still valid for another %ds",
            user,
            expires_at - now,
        )
        return False
    return True


def revoke_token(
    client,
    revocation_url,
    token_with_privilege,
    token_revoke,
    token_type_hints=None,
):
    """
    Revoke a token
    :param client: the client
    :param revocation_url: the revocation url
    :param token_with_privilege: the token with permission to revoke
    :param token_revoke: the token to revoke
    :param token_type_hints: the types of token
    :return:
    """

    if token_type_hints is None:
        token_type_hints = ["refresh_token", "access_token"]

    if token_revoke is None:
        token_revoke = {}

    for token_type_hint in token_type_hints:
        client.post(
            revocation_url,
            data={
                "token": token_revoke[token_type_hint],
                "token_type_hint": token_type_hint,
            },
            auth=(client.client_id, client.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            token=token_with_privilege,
        )


def delete_associations(associations):
    """
    Delete a set of TokenUserAgentAssociations
    """
    try:
        # delete these tokens
        associations.delete()
    except ProtectedError:
        logger.warning(
            "Unable to delete tokens for user agents during garbage "
            "collection due to PROTECT foreign key"
        )
        sentry_sdk.capture_exception()
    except IntegrityError:
        logger.warning(
            "Unable to delete tokens for user agents during garbage "
            "collection due to database integrity issue"
        )
        sentry_sdk.capture_exception()
    except DatabaseError:
        logger.warning(
            "Unable to delete tokens for user agents during garbage "
            "collection due to unknown database error"
        )
        sentry_sdk.capture_exception()
    except OperationalError:
        logger.warning(
            "Unable to delete tokens for user agents during garbage "
            "collection due to unknown database operational error"
        )
        sentry_sdk.capture_exception()
    except Exception:
        logger.exception(
            "Unable to delete tokens for user agents during garbage "
            "collection due to unknown other error"
        )
        sentry_sdk.capture_exception()
