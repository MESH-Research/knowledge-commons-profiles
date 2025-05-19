"""OAuth initializer"""

import base64
import json
import urllib.parse as urlparse
from urllib.parse import urlencode

from authlib.integrations.django_client import OAuth
from authlib.jose.errors import InvalidClaimError
from authlib.oidc.core import CodeIDToken
from django.conf import settings

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
