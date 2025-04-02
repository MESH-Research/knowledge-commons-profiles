"""
Middleware for profiles
"""

import datetime
import hashlib
from urllib.parse import unquote

import phpserialize
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth import logout
from django.db import OperationalError
from django.db import connections

User = get_user_model()


class WordPressAuthMiddleware:
    """
    Middleware to authenticate users based on WordPress auth cookie
    """

    def __init__(self, get_response):
        """
        Initialize the middleware.

        :param get_response: a callable that produces a response object
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request and authenticate the user if a WordPress cookie is
        present.

        :param request: The request object
        :return: The response to the request
        """
        # Only process if user is not already authenticated
        if not request.user.is_authenticated:
            wordpress_cookie = self.get_wordpress_cookie(request)
            if wordpress_cookie:

                # this can fail if WordPress database is not available
                # although we are in deeper trouble than that if this happens
                try:
                    user = self.authenticate_wordpress_session(
                        wordpress_cookie
                    )
                except OperationalError:
                    request.session["wordpress_logged_in"] = False
                    return self.get_response(request)

                if user:
                    # If the authentication is successful, log the user in
                    login(request, user)
                    request.session["wordpress_logged_in"] = True
        # if the user is already authenticated, re-check their WordPress
        # session if they were logged in by WordPress
        elif (
            request.session.get("wordpress_logged_in", True)
            and not request.user.is_superuser
        ):
            wordpress_cookie = self.get_wordpress_cookie(request)

            if not wordpress_cookie:
                # If the cookie is not present, log the user out
                logout(request)
                request.session["wordpress_logged_in"] = False
                return self.get_response(request)

            user = self.authenticate_wordpress_session(wordpress_cookie)
            if not user:
                # If the auth is not successful, log the user out
                logout(request)
                request.session["wordpress_logged_in"] = False
                return self.get_response(request)
        # user is logged in, but there is no value set for
        # "wordpress_logged_in" and they are not a superuser
        elif request.user.is_authenticated and not request.user.is_superuser:
            request.session["wordpress_logged_in"] = False
            logout(request)

        # Return the response
        return self.get_response(request)

    @staticmethod
    def get_wordpress_cookie(request):
        """Extract WordPress auth cookie from request"""
        for key in request.COOKIES:
            if key.startswith("wordpress_logged_in_"):
                return unquote(request.COOKIES[key])
        return None

    @staticmethod
    def get_wordpress_values(username):
        """
        Get the WordPress user ID and email associated with the given username

        :param username: the WordPress username
        :return: a tuple with the user ID and email, or None if not found
        """
        with connections["wordpress_dev"].cursor() as cursor:
            # Get the user ID and email for the given username
            # This is stored in the wp_users table
            cursor.execute(
                """
                SELECT ID, user_email, user_pass
                FROM wp_users
                WHERE user_login = %s
                """,
                [username],
            )
            user_id = cursor.fetchone()
            if not user_id:
                return None

            user_id, user_email, user_password = user_id

            return user_id, user_email, user_password

    @staticmethod
    def get_meta_value(user_id):
        """
        Get the session token for the given WordPress user_id
        """
        with connections["wordpress_dev"].cursor() as cursor:
            # Get the session token for the given user_id
            # This is stored in the meta_value field of the wp_usermeta table
            # The meta_key field is 'session_tokens'
            cursor.execute(
                """
                SELECT meta_value
                FROM wp_usermeta
                WHERE user_id = %s AND meta_key = 'session_tokens'
                """,
                [user_id],
            )
            meta_vals = cursor.fetchone()
            if not meta_vals:
                # If there is no user with the given ID, return None
                return None

            meta_value = meta_vals[0]

            # The meta_value is serialized using php serialize
            return phpserialize.unserialize(meta_value.encode())

    def authenticate_wordpress_session(self, cookie_value):
        """Verify WordPress session and return corresponding Django user"""

        # Parse WordPress auth cookie
        username, expiration, token, _ = cookie_value.split("|")

        # sha256 hash the token as this is how WordPress stores it
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # get user ID and email from WordPress database
        user_id, user_email, _ = self.get_wordpress_values(username)

        # get the session from the database
        meta_value_dict = self.get_meta_value(user_id=user_id)

        # look through sessions for non-expired and matching hashes
        for key, val in meta_value_dict.items():
            # first, check we haven't expired
            dt = datetime.datetime.fromtimestamp(
                val[b"expiration"],
                tz=datetime.UTC,
            )

            if dt < datetime.datetime.now(tz=datetime.UTC) or int(
                expiration
            ) != int(val[b"expiration"]):
                # expired
                continue

            if token_hash.encode() != key:
                # hash doesn't match. Invalid session.
                continue

            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": user_email, "is_active": True},
            )

            return user

        return None
