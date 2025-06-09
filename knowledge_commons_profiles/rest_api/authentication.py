"""
Authentication for the REST API

"""

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission


class StaticBearerAuthentication(BaseAuthentication):
    """
    Checks for “Authorization: Bearer <MY_STATIC_TOKEN>” and if it matches,
    returns an AnonymousUser + the token. Otherwise, it does nothing (so the
    request is treated as anonymous).
    """

    keyword = "Bearer"
    static_token = settings.STATIC_API_BEARER

    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        parts = auth.split()

        bearer_parts_length = 2

        if len(parts) != bearer_parts_length or parts[0] != self.keyword:
            # no credentials → let other authenticators run (or fallback to
            # anon)
            return None

        token = parts[1]
        if token != self.static_token:
            # invalid token
            return None

        # We don't have a real User to return; by convention we can return
        # an AnonymousUser instance but then look at request.auth in the view.
        return AnonymousUser(), token


class HasStaticBearerToken(BasePermission):
    """
    Only allow if request.auth (the token from your StaticBearerAuthentication)
    exactly matches settings.STATIC_API_BEARER.
    """

    def has_permission(self, request, view):
        return request.auth == settings.STATIC_API_BEARER
