"""OAuth initializer"""

import base64
import binascii
import hashlib
import json
import logging
import os
import time
import urllib.parse as urlparse
from urllib.parse import urlencode

import requests
import sentry_sdk
import tldextract
from authlib.integrations.django_client import OAuth
from authlib.jose import jwt
from authlib.jose.errors import InvalidClaimError
from authlib.oidc.core import CodeIDToken
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import modes
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import DatabaseError
from django.db import IntegrityError
from django.db import OperationalError
from django.db.models import ProtectedError
from django.shortcuts import redirect
from idna import IDNAError
from jwt.exceptions import InvalidTokenError

from knowledge_commons_profiles.rest_api.idms_api import APIClient
from knowledge_commons_profiles.rest_api.idms_api import APIClientConfig
from knowledge_commons_profiles.rest_api.idms_api import AssociationUpdate
from knowledge_commons_profiles.rest_api.idms_api import EventType

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
    next_url = data.get("callback_next")
    code = request.GET.get("code")

    return code, next_url


def pack_state(next_url):
    """
    B64 encode a next URL
    """
    # Pack next_url into state and b64 encode
    return base64.urlsafe_b64encode(
        json.dumps({"callback_next": next_url}).encode()
    ).decode()


def forward_url(request):
    """
    Forward the code to the next URL (return a redirect) or return None
    """
    # attempt to decode state to see if there is a next URL
    # if there is, we want to forward the code to the next URL for it to decode
    # If there is no next URL, we want to decode the code here and login
    try:
        code, next_url = extract_code_next_url(request)

        if next_url and next_url != "":
            url_parts = generate_next_url(code, next_url, request)

            try:
                # parse netloc into subdomain, base domain etc.
                extract_result = tldextract.extract(next_url)

                # validate that the next URL is in the allowed list
                # settings.ALLOWED_CILOGON_FORWARDING_DOMAINS
                domain_to_check = (
                    (extract_result.domain + "." + extract_result.suffix)
                    if extract_result.suffix and extract_result.suffix != ""
                    else extract_result.domain
                )
                if (
                    domain_to_check
                ) in settings.ALLOWED_CILOGON_FORWARDING_DOMAINS:
                    logger.info("Forwarding CILogon code to %s", next_url)
                    return redirect(str(urlparse.urlunparse(url_parts)))

                message = (
                    f"Disallowed CILogon code forwarding URL: "
                    f"{next_url} with parts: "
                    f"{domain_to_check}"
                )
                logger.warning(message)
            except (ValueError, IDNAError, UnicodeDecodeError, OSError) as e:
                sentry_sdk.capture_exception(e)
                logger.exception(
                    "Exception parsing and validating next_url: %s", next_url
                )

    except (
        json.JSONDecodeError,
        TypeError,
        binascii.Error,
        ValueError,
        UnicodeDecodeError,
    ):
        message = (
            f"Unspecified error parsing CILogon state: "
            f"{request.GET.get("state")}"
        )
        logger.exception(message)

    return None


def store_session_variables(request, token, userinfo_input=None):
    """
    Store session variables "userinfo" and "oidc_token"
    """
    logger.info("Storing new token")

    userinfo = userinfo_input

    if not userinfo:
        userinfo = request.session.get("oidc_userinfo", None)

    if token:
        request.session["oidc_token"] = token
        if "userinfo" in token:
            userinfo = token["userinfo"]

    if userinfo:
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


def get_cilogon_jwks():
    """
    Fetch and cache CILogon's JWKS
    """
    cache_key = "cilogon_jwks"
    jwks = cache.get(cache_key)

    if not jwks:
        try:
            response = requests.get(
                "https://cilogon.org/oauth2/certs", timeout=10
            )
            response.raise_for_status()
            jwks = response.json()
            # Cache for 1 hour
            cache.set(cache_key, jwks, 3600)
        except requests.RequestException:
            message = "Failed to fetch JWKS"
            logger.exception(message)
            raise

    return jwks


# Alternative approach if you want more control over validation
def verify_and_decode_cilogon_jwt(id_token):
    """
    Manual verification approach with Authlib
    """
    jwks = get_cilogon_jwks()

    # Verify and decode
    return jwt.decode(
        id_token,
        jwks,
        claims_options={
            "iss": {"essential": True, "value": "https://cilogon.org"},
            "aud": {
                "essential": False,
                "value": settings.CILOGON_CLIENT_ID,
            },
            "exp": {"essential": True},
        },
    )


class SecureParamEncoder:
    """
    Encrypt and encode data for URL transmission
    """

    def __init__(self, shared_secret: str):
        # Derive a 32-byte key from any length secret
        self.key = hashlib.sha256(shared_secret.encode()).digest()

    def encode(self, data: dict) -> str:
        """
        Encrypt and encode data
        :param data: a dictionary of querystring parameters
        """
        json_data = json.dumps(data).encode()

        # Generate random IV
        iv = os.urandom(16)

        # Pad data to block size
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(json_data) + padder.finalize()

        # Encrypt
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()

        # Combine IV + encrypted data
        result = iv + encrypted
        return base64.urlsafe_b64encode(result).decode()

    def decode(self, encrypted_param: str) -> dict:
        """
        Decode and decrypt data
        """
        data = base64.urlsafe_b64decode(encrypted_param.encode())

        # Extract IV and encrypted data
        iv = data[:16]
        encrypted = data[16:]

        # Decrypt
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted) + decryptor.finalize()

        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        json_data = unpadder.update(padded_data) + unpadder.finalize()

        return json.loads(json_data.decode())


def get_secure_userinfo(request) -> tuple[bool, dict | None]:
    """
    Get the token and userinfo with proper validation
    """
    # First try session data
    userinfo = request.session.get("oidc_userinfo", {})

    # Validate session data
    if userinfo and userinfo.get("sub"):
        return True, userinfo

    # Fallback to signed userinfo from GET parameter
    encoder = SecureParamEncoder(settings.STATIC_API_BEARER)

    # decode the GET parameter with secure userinfo on AES
    try:
        userinfo_querystring = request.GET.get("userinfo", None)

        if not userinfo_querystring:
            return False, None

        userinfo_signed = encoder.decode(request.GET.get("userinfo"))
    except Exception:
        message = "Failed to decrypt userinfo"
        logger.exception(message)
        return False, None

    if not userinfo_signed:
        return False, None

    # now check signature on GET parameter
    try:
        userinfo = verify_and_decode_cilogon_jwt(
            userinfo_signed.get("userinfo")
        )

        store_session_variables(
            request=request, token=None, userinfo_input=userinfo
        )

        if userinfo and userinfo.get("sub"):
            return True, userinfo
    except (InvalidTokenError, ValueError, Exception):
        message = "Failed to verify and decode CILogon userinfo"
        logger.exception(message)
        sentry_sdk.capture_exception()

    return False, None


def send_association_message(sub: str, kc_id: str):
    """
    Send an association message to the webhook
    :param sub: the subject
    :param kc_id: the kc id
    """

    for base_endpoint in settings.WORKS_UPDATE_ENDPOINTS:

        config = APIClientConfig(
            base_url=base_endpoint,
            timeout=30,
            max_retries=3,
            backoff_factor=0.5,
        )
        client = APIClient(config)

        association_updates = [
            AssociationUpdate(
                id=sub,
                kc_id=kc_id,
                event=EventType.ASSOCIATED,
            ),
        ]

        try:
            # Send updates
            response = client.send_association(
                endpoint="/api/webhooks/user_data_update",
                idp="cilogon",
                associations=association_updates,
                headers={
                    "Authorization": "Bearer " + settings.WEBHOOK_TOKEN,
                },
            )

            if response.data:
                message = "Success! Response: %s"
                logger.info(message, json.dumps(response.data, indent=2))
            else:
                message = "Success! Raw response: %s"
                logger.info(message, response.raw_response)

        except ValueError:
            message = "Validation error: %s"
            logger.exception(message)
        except requests.exceptions.ConnectionError:
            message = "Failed to connect to the API server"
            logger.exception(message)
        except requests.exceptions.Timeout:
            message = "Request timed out"
            logger.exception(message)
        except requests.exceptions.HTTPError:
            message = "HTTP error occurred"
            logger.exception(message)
        except requests.exceptions.RequestException:
            message = "Request failed"
            logger.exception(message)
        except Exception:
            message = "Unexpected error"
            logger.exception(message)

        else:
            return

    return
