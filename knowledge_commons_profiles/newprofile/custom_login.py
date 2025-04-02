"""
A custom login view for WordPress compatibility
"""

import hashlib
import hmac
import math
import time
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect

from config.settings.base import env
from knowledge_commons_profiles.newprofile.api import API
from knowledge_commons_profiles.newprofile.middleware import (
    WordPressAuthMiddleware,
)
from knowledge_commons_profiles.newprofile.models import WpUser

# WordPress constant: DAY_IN_SECONDS = 86400
DAY_IN_SECONDS = 86400


def get_wp_session_token(request):
    """
    Return the token from a WordPress auth cookie
    """
    try:
        cookie = WordPressAuthMiddleware.get_wordpress_cookie(request)
        return cookie.split("|")[2]
    except IndexError:
        return None


def wp_nonce_tick(action=-1):
    """
    Returns the time-dependent variable for nonce creation.

    This is a port from WordPress's wp_nonce_tick function that calculates
    the tick used for nonce creation based on the current time and nonce
    lifespan.

    Args:
        action: The action string that might be used for more targeted filters

    Returns:
        int: The tick value used for nonce generation
    """

    # Calculate and return the tick value
    return math.ceil(time.time() / (DAY_IN_SECONDS / 2))


def wp_hash(data, scheme="auth"):
    """
    Creates a hash of data using HMAC-MD5 with a WordPress-specific salt.

    Args:
        data: The data to hash
        scheme: The scheme to use for retrieving the salt ('auth',
        'secure_auth', 'logged_in', 'nonce')

    Returns:
        str: Hashed data using HMAC-MD5
    """
    # Get the appropriate salt based on the scheme
    salt = env.str("NONCE_SALT", default="")

    # Create HMAC-MD5 hash
    return hmac.new(
        salt.encode("utf-8"), data.encode("utf-8"), hashlib.md5
    ).hexdigest()


def wp_create_nonce(action="logout", request=None):
    """
    Creates a cryptographic token tied to a specific action, user, and
    time period.

    Args:
        action: The action for which the nonce is being created
        request: The request object

    Returns:
        str: A 10-character nonce
    """
    # Get current WordPress user ID
    api = API(request, request.user.username, use_wordpress=True, create=False)

    try:
        user = api.wp_user
    except WpUser.DoesNotExist:
        return ""
    except Exception:  # noqa: BLE001
        return ""

    uid = int(user.id) if hasattr(user, "id") else 0

    # Get session token
    token = get_wp_session_token(request)

    # Get nonce tick
    nonce_tick = math.ceil(time.time() / (DAY_IN_SECONDS / 2))

    # Create and return the nonce
    nonce_str = f"{nonce_tick}|{action}|{uid}|{token}"
    return wp_hash(nonce_str, "nonce")[-12:-2]


def login_required(
    function=None, redirect_field_name="redirect_to", login_url=None
):
    """
    Custom login_required that uses the custom redirect parameter name.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            path = request.build_absolute_uri()
            login_url_with_redirect = get_login_url(path)
            return HttpResponseRedirect(login_url_with_redirect)

        return _wrapped_view

    if function:
        return decorator(function)
    return decorator


def get_login_url(next_url=None):
    """Generate a login URL with the custom redirect parameter name."""
    base_url = settings.LOGIN_URL
    if next_url:
        params = {
            getattr(settings, "REDIRECT_FIELD_NAME", "redirect_to"): next_url
        }
        return f"{base_url}?{urlencode(params)}"
    return base_url
