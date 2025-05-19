"""OAuth initializer"""

import base64
import binascii
import contextlib
import json
import logging
import urllib.parse as urlparse
from urllib.parse import urlencode

import sentry_sdk
import tldextract
from authlib.integrations.django_client import OAuth
from authlib.jose.errors import InvalidClaimError
from authlib.oidc.core import CodeIDToken
from django.conf import settings
from django.shortcuts import redirect
from idna import IDNAError

logger = logging.getLogger(__name__)

oauth = OAuth()

oauth.register(
    name="cilogon",
    client_id=settings.CILOGON_CLIENT_ID,
    client_secret=settings.CILOGON_CLIENT_SECRET,
    server_metadata_url="https://cilogon.org/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile org.cilogon.userinfo offline_access"
    },
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
    Store session variables
    """
    userinfo = token["userinfo"]
    request.session["oidc_token"] = token
    request.session["oidc_userinfo"] = userinfo

    return userinfo
