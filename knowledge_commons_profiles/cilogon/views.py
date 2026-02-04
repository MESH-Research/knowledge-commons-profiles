"""
Views for CILogon

"""

import csv
import html
import io
import logging
import re
from enum import IntEnum
from typing import Any
from uuid import uuid4

import requests
import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session as DjangoSession
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.core.validators import validate_email
from django.db import IntegrityError
from django.db import transaction
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from knowledge_commons_profiles.cilogon.forms import UploadCSVForm
from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import delete_associations
from knowledge_commons_profiles.cilogon.oauth import find_user_and_login
from knowledge_commons_profiles.cilogon.oauth import forward_url
from knowledge_commons_profiles.cilogon.oauth import (
    get_forwarding_state_for_proxy,
)
from knowledge_commons_profiles.cilogon.oauth import get_oauth_redirect_uri
from knowledge_commons_profiles.cilogon.oauth import get_secure_userinfo
from knowledge_commons_profiles.cilogon.oauth import (
    is_request_from_actual_domain,
)
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import revoke_token
from knowledge_commons_profiles.cilogon.oauth import send_association_message
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.common.profiles_email import (
    sanitize_email_for_dev,
)
from knowledge_commons_profiles.common.profiles_email import (
    send_knowledge_commons_email,
)
from knowledge_commons_profiles.newprofile.mailchimp import (
    hcommons_add_new_user_to_mailchimp,
)
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.pages.models import SitePage
from knowledge_commons_profiles.rest_api.sync import ExternalSync
from knowledge_commons_profiles.rest_api.utils import logout_all_endpoints_sync

logger = logging.getLogger(__name__)

# Maximum length for full name field
MAX_FULL_NAME_LENGTH = 100


class RedirectBehaviour(IntEnum):
    """
    Enum for whether to flush logout to other sources
    """

    REDIRECT = 1
    NO_REDIRECT = 2


class FlushLogoutBehaviour(IntEnum):
    """
    Enum for redirect behaviour
    """

    FLUSH_LOGOUT = 1
    NO_FLUSH_LOGOUT = 2


def cilogon_login(request):
    """
    The login redirect for OAuth
    :param request: the request
    """
    # flush the session
    app_logout(request, redirect_behaviour=RedirectBehaviour.NO_REDIRECT)
    request.session.flush()

    # Build redirect URI, substituting registered domain if using domain proxy
    redirect_uri = get_oauth_redirect_uri(request)

    # Get state with forwarding URL if using domain proxy
    state = get_forwarding_state_for_proxy()

    return oauth.cilogon.authorize_redirect(request, redirect_uri, state=state)


def callback(request):
    """
    The callback view for OAuth
    :param request: request
    """

    # Forward the code to the next URL if:
    # 1. There's a valid forwarding URL in the state
    # 2. We're NOT on the actual domain (i.e., we're on the proxy/registered
    # domain)
    # When using domain proxy, the registered domain forwards to the actual
    # domain
    forwarding_url = forward_url(request)
    if forwarding_url and not is_request_from_actual_domain(request):
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
    sub_association: SubAssociation = SubAssociation.objects.filter(
        sub=userinfo.get("sub", "")
    ).first()

    # do we have a sub->profile?
    if sub_association:
        # Wrap database operations in a transaction to ensure consistency
        with transaction.atomic():
            # update the sub with an idp_name
            sub_association.idp_name = userinfo.get("idp_name", "")
            sub_association.save()

            # yes, found a sub->profile, log them in
            # (find_user_and_login has its own nested transaction for user
            # creation)
            find_user_and_login(request, sub_association)

            logger.info("Received userinfo: %s", userinfo)

            # test whether the userinfo has an email that we don't know about
            if (
                userinfo.get("email")
                and userinfo.get("email") != sub_association.profile.email
            ):
                if userinfo.get("email") not in sub_association.profile.emails:
                    sub_association.profile.emails.append(
                        userinfo.get("email")
                    )
                    sub_association.profile.save()

        # update user network affiliations (outside transaction - external call)
        ExternalSync.sync(profile=sub_association.profile)

        # return to the profile page
        return redirect(reverse("my_profile"))

    # no, no user. Redirect to the profile association page
    return redirect(reverse("associate"))


# ruff: noqa: PLR0913
# ruff: noqa: C901
def app_logout(
    request,
    redirect_behaviour: RedirectBehaviour = RedirectBehaviour.REDIRECT,
    user_name=None,
    user_agent=None,
    apps=None,
    flush_behaviour: FlushLogoutBehaviour = FlushLogoutBehaviour.FLUSH_LOGOUT,
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

    logger.debug(
        "Logging out user %s with user agent %s on %s",
        user_name,
        user_agent,
        apps,
    )

    # send api requests to logout
    if flush_behaviour == FlushLogoutBehaviour.FLUSH_LOGOUT:
        msg = f"Flushing logout behaviour to all endpoints for {user_name}"
        logout_all_endpoints_sync(username=user_name, request=request)

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
    try:
        user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        msg = f"Unable to find correlating user for logout request {user_name}"
        logger.warning(msg)
        user = None

    if user:
        msg = (
            f"Logging out {user_name} (ID: {user.id}) locally "
            f"and deleting all sessions"
        )
        logger.info(msg)

        to_delete: list[DjangoSession] = []

        for session in DjangoSession.objects.all():
            decoded = session.get_decoded()
            if decoded.get("_auth_user_id") == str(user.pk):
                to_delete.append(session)

        for session in to_delete:
            session.delete()

    logout(request)

    if redirect_behaviour == RedirectBehaviour.REDIRECT:
        # redirect the user to the home page
        # TODO: proper redirect
        return redirect("/")

    return None


@staff_member_required
def manage_roles(request, user_name):

    # first, get a profile object
    profile = get_object_or_404(Profile, username=user_name)

    if request.method == "POST":
        # remove an override
        if role_to_delete := request.POST.get("role_to_delete"):
            if role_to_delete in profile.role_overrides:
                msg = f"Removed role {role_to_delete} from {profile.username}"
                logger.info(msg)
                profile.role_overrides.remove(role_to_delete)
                profile.save()
        if role_to_add := request.POST.get("role_to_add"):
            if role_to_add not in profile.role_overrides:
                msg = f"Added role {role_to_add} to {profile.username}"
                logger.info(msg)
                profile.role_overrides.append(role_to_add)
                profile.role_overrides = sorted(profile.role_overrides)
                profile.save()

        # remove a legacy Comanage role
        if comanage_to_delete := request.POST.get("comanage_role_to_delete"):
            msg = (
                f"Removed Comanage role {comanage_to_delete}"
                f" from {profile.username}"
            )
            logger.info(msg)
            _remove_comanage_role(profile, comanage_to_delete)

    # build the organizations, after syncing the profile
    final_orgs_api = _build_organizations_list(profile=profile, api_only=True)
    final_orgs = _build_organizations_list(profile=profile, api_only=False)
    final_orgs_manual = [
        final_org
        for final_org in final_orgs
        if final_org not in final_orgs_api
    ]

    co_manage_roles = Role.objects.filter(person__user=profile)

    # build a context
    context = {
        "memberships_api": final_orgs_api,  # memberships from APIs
        "memberships_manual": final_orgs_manual,  # memberships added manually
        "memberships_applied": final_orgs,  # all memberships as applied
        "profile": profile,
        "co_manage_roles": co_manage_roles,
    }

    return render(request, "cilogon/roles.html", context)


@login_required
def manage_login(request, username):

    # first, get a profile object
    try:
        # for regular users, always fetch their own profile
        if not request.user.is_staff:
            username = request.user.username

        profile = Profile.objects.get(username=username)
    except Profile.DoesNotExist:
        profile = None

    # handle POST options
    if request.method == "POST":
        # remove a secondary email
        if request.POST.get("email_remove"):
            _remove_secondary_email(profile, request)
            return redirect(reverse("manage_login", args=[username]))

        # add a new secondary email
        if request.POST.get("new_email"):
            if _add_secondary_email(profile, request):
                return redirect(
                    reverse("manage_login", args=[username])
                    + "?new_email=true"
                )
            return redirect(
                reverse("manage_login", args=[username]) + "?error=true"
            )

        # make an email primary
        if request.POST.get("email_primary"):
            _make_email_primary(profile, request)
            return redirect(reverse("manage_login", args=[username]))

        # remove an IDP owned by the user (default action on POST if not
        # handled above)
        idp_id = request.POST.get("idp_id")
        sas = SubAssociation.objects.filter(
            id=idp_id, profile__username=request.user.username
        )
        sas.delete()

    # get the subs from the db
    subs = SubAssociation.objects.filter(profile__username=username)

    # build the organizations, after syncing the profile
    final_orgs = _build_organizations_list(profile)

    # determine the self-service networks that the user is not a member of
    open_networks = settings.OPEN_REGISTRATION_NETWORKS
    open_networks_user_not_enrolled = [
        network for network in open_networks if network[0] not in final_orgs
    ]

    # build an alert message if needed
    msg = ""
    new_email_msg = request.GET.get("new_email", "")
    error_msg = request.GET.get("error", "")

    if new_email_msg:
        msg = (
            "We have sent an email to your new email address. "
            "Please check your inbox and click the link to verify it."
        )

    if error_msg:
        msg = "This email address is already in use"

    # build a context
    context = {
        "login_methods": subs,
        "memberships": final_orgs,
        "profile": profile,
        "msg": msg,
        "networks": open_networks_user_not_enrolled,
        "open_networks": [open_network[0] for open_network in open_networks],
    }

    return render(request, "cilogon/manage.html", context)


@login_required
@require_http_methods(["POST"])
def self_join_network(request, username, network):
    # check the network allows users to subscribe
    profile, username = (
        get_profile_and_username_and_check_open_network_security(
            network, request, username
        )
    )

    # add the network to the profile (only if not already a member)
    if network not in profile.role_overrides:
        profile.role_overrides.append(network)
        profile.save()

    return redirect(reverse("manage_login", args=[username]))


def get_profile_and_username_and_check_open_network_security(
    network, request: WSGIRequest | Any, username: str | Any
) -> tuple[Profile, str]:
    if not any(
        open_network[0] == network
        for open_network in settings.OPEN_REGISTRATION_NETWORKS
    ):
        raise Http404

    # get a profile object
    if not request.user.is_staff:
        username = request.user.username

    try:
        profile = Profile.objects.get(username=username)
    except Profile.DoesNotExist:
        profile = None

    if not profile:
        raise Http404
    return profile, username


@login_required
@require_http_methods(["POST"])
def self_leave_network(request, username, network):
    profile, username = (
        get_profile_and_username_and_check_open_network_security(
            network, request, username
        )
    )

    if request.POST.get("membership_to_leave"):
        # Only remove if user is actually a member
        if network in profile.role_overrides:
            profile.role_overrides.remove(network)
            profile.save()

    return redirect(reverse("manage_login", args=[username]))


def _remove_comanage_role(profile: Profile, comanage_role_id):
    role = Role.objects.filter(id=comanage_role_id).first()
    if role:
        role.delete()


def _build_organizations_list(
    profile: Profile | None, api_only=False
) -> list[Any]:
    orgs = {}
    if profile:
        # initiate an external sync
        orgs = ExternalSync.sync(profile=profile, cache=False)
    else:
        return []

    final_orgs = []
    for org, is_member in orgs.items():
        # if the user is a member of the org, add it to the list
        if is_member:
            final_orgs.append(org)

    if api_only:
        return final_orgs

    # add any manual memberships
    for org in profile.role_overrides:
        if org not in final_orgs:
            final_orgs.append(org)

    return final_orgs


def _remove_secondary_email(profile: Profile | None, request):
    email = request.POST.get("email_remove", "")
    if email and email in profile.emails:
        profile.emails.remove(email)
        profile.save()


def _add_secondary_email(profile: Profile | None, request):
    email = request.POST.get("new_email", "")

    # check the email doesn't exist somewhere else
    profiles = Profile.objects.filter(email=email)
    if profiles.exists():
        messages.error(request, "Email already in use")
        return False

    profiles = Profile.objects.filter(emails__contains=[email])

    if profiles.exists():
        messages.error(request, "Email already in use")
        return False

    # send a verification email
    send_new_email_verify(email, profile, request)
    return True


@login_required
def new_email_verified(request, secret_key):
    """
    The activation view clicked by a user from email
    """

    EmailVerification.garbage_collect()

    # get the verification by secret key or 404
    verify: EmailVerification = get_object_or_404(
        EmailVerification, secret_uuid=secret_key
    )

    # add the email
    if verify.sub not in verify.profile.emails:
        verify.profile.emails.append(verify.sub)
        verify.profile.emails = sorted(verify.profile.emails)
        verify.profile.save()

    # delete the verification as it's no longer needed
    verify.delete()

    # TODO: send a webhook sync request

    # redirect the user to their Profile page
    return redirect(reverse("manage_login", args=[request.user.username]))


def _make_email_primary(profile: Profile | None, request):
    email = request.POST.get("email_primary", "")

    # Only proceed if email is valid and in the secondaries list
    if not email or email not in profile.emails:
        return

    # first, add the existing primary to the secondaries
    if profile.email not in profile.emails:
        profile.emails.append(profile.email)
        profile.emails = sorted(profile.emails)

    # now add the old secondary as the primary email
    profile.email = email

    # remove the new primary from the secondaries
    profile.emails.remove(email)

    # sort the emails
    profile.emails = sorted(profile.emails)

    # save the object
    profile.save()


@transaction.atomic
def register(request):
    # first, see whether we have an unassociated user
    userinfo_is_valid: bool
    userinfo: dict | None
    userinfo_is_valid, userinfo = get_secure_userinfo(request)

    # if the userinfo is not valid, redirect to login
    if not userinfo_is_valid:
        return redirect(reverse("login"))

    # check the user is not properly logged in and redirect if so
    user = request.user
    if user and user.is_authenticated:
        return redirect(reverse("my_profile"))

    context = {"cilogon_sub": userinfo.get("sub", "")}

    # Check that we have a valid cilogon_sub before proceeding
    if not context["cilogon_sub"]:
        logger.error("The sub was not passed to the register view")
        return render(request, "cilogon/registration_error.html")

    # Load terms of service content for the registration form
    terms_page = SitePage.objects.filter(slug="terms-of-service").first()
    if terms_page:
        context["terms_content"] = terms_page.body
        context["terms_title"] = terms_page.title

    # Load open registration networks for optional membership
    context["open_networks"] = settings.OPEN_REGISTRATION_NETWORKS

    if request.method == "POST":
        email, full_name, username = extract_form_data(
            context, request, userinfo
        )

        errored = False
        errored = validate_form(email, full_name, request, username)

        if not request.POST.get("accept_terms"):
            errored = True
            messages.error(request, "You must accept the terms and conditions")

        if errored:
            return render(request, "cilogon/new_user.html", context)

        # Sanitize the full name before storage (defense in depth)
        sanitized_name = sanitize_full_name(full_name)

        # Explicit pre-creation checks to catch race conditions early
        # (validate_form already checks, but a double-click can slip through)
        if Profile.objects.filter(username=username).exists():
            messages.error(request, "This username already exists")
            return render(request, "cilogon/new_user.html", context)

        if Profile.objects.filter(email=email).exists():
            messages.error(request, "This email already exists")
            return render(request, "cilogon/new_user.html", context)

        if Profile.objects.filter(emails__contains=[email]).exists():
            messages.error(request, "This email already exists")
            return render(request, "cilogon/new_user.html", context)

        if User.objects.filter(username=username).exists():
            messages.error(request, "This username already exists")
            return render(request, "cilogon/new_user.html", context)

        # Collect selected networks from the form
        selected_networks = [
            network_code
            for network_code, _ in settings.OPEN_REGISTRATION_NETWORKS
            if request.POST.get(f"network_{network_code}")
        ]

        try:
            # Create the Profile object with any selected network memberships
            profile = Profile.objects.create(
                name=sanitized_name,
                username=username,
                email=email,
                role_overrides=sorted(selected_networks),
            )

            # Create the corresponding Django User
            User.objects.create(username=username, email=email)

            # Do NOT create SubAssociation yet - wait for email verification
            # Do NOT log in yet - wait for email verification
        except IntegrityError:
            # Race condition: another request created the user between our
            # check and creation. Do NOT log in - just show error and return.
            msg = (
                "IntegrityError during registration for username=%s email=%s "
                "(likely double-submit race condition)"
            )
            logger.warning(
                msg,
                username,
                email,
            )
            err_message = (
                "This account was just created. Please try logging "
                "in instead."
            )
            messages.error(
                request,
                err_message,
            )
            return render(request, "cilogon/new_user.html", context)

        # Send email verification - user must confirm before they can log in
        send_registration_verification_email(
            email=email,
            profile=profile,
            cilogon_sub=context["cilogon_sub"],
            request=request,
        )

        # Redirect to confirmation page (tell user to check their email)
        return redirect(reverse("confirm"))

    return render(request, "cilogon/new_user.html", context)


def extract_form_data(context, request, userinfo):
    # get the form data
    email = request.POST.get("email", None)
    username = request.POST.get("username", None)
    full_name = request.POST.get("full_name", None)

    first_name = None
    last_name = full_name

    if full_name:
        try:
            parts = full_name.split(" ")
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        except (IndexError, AttributeError):
            first_name = None
            last_name = full_name

    context.update(
        {
            "email": request.POST.get("email", userinfo.get("email", "")),
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "userinfo": userinfo,
        }
    )
    return email, full_name, username


def validate_form(email, full_name, request, username):
    errored = False

    # check none of these are blank
    if not email or not username or not full_name:
        errored = True
        messages.error(request, "Please fill in all fields")
        # Early return since we can't validate empty values
        return errored

    # Validate email format using Django's EmailValidator
    try:
        validate_email(email)
    except DjangoValidationError:
        errored = True
        messages.error(request, "Please enter a valid email address")

    # Validate username: alphanumeric, underscores, hyphens only
    # Length between 3 and 30 characters
    username_pattern = r"^[a-zA-Z0-9_-]{3,30}$"
    if not re.match(username_pattern, username):
        errored = True
        messages.error(
            request,
            "Username must be 3-30 characters and contain only letters, "
            "numbers, underscores, and hyphens",
        )

    # Validate full name: reasonable length and no HTML/script tags
    # Strip any HTML tags for XSS prevention
    if len(full_name) > MAX_FULL_NAME_LENGTH:
        errored = True
        messages.error(
            request,
            f"Full name must be {MAX_FULL_NAME_LENGTH} characters or less",
        )

    # Check for HTML/script injection attempts
    if _contains_html_or_script(full_name):
        errored = True
        messages.error(
            request, "Full name contains invalid characters or formatting"
        )

    # check whether this email already exists
    profile = Profile.objects.filter(email=email).first()
    if profile:
        errored = True
        messages.error(request, "This email already exists")

    profile = Profile.objects.filter(emails__contains=[email]).first()
    if profile:
        errored = True
        messages.error(request, "This email already exists")

    # check whether this username already exists
    profile = Profile.objects.filter(username=username).first()
    if profile:
        errored = True
        messages.error(request, "This username already exists")

    return errored


def _contains_html_or_script(text: str) -> bool:
    """
    Check if text contains HTML tags or script injection attempts.
    Returns True if potentially dangerous content is found.
    """
    if not text:
        return False

    # Check for HTML tags (including self-closing)
    html_pattern = r"<[^>]+>"
    if re.search(html_pattern, text):
        return True

    # Check for common XSS patterns
    xss_patterns = [
        r"javascript:",
        r"on\w+\s*=",  # onclick, onerror, etc.
        r"data:",
        r"vbscript:",
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in xss_patterns)


def sanitize_full_name(full_name: str) -> str:
    """
    Sanitize a full name by escaping HTML entities and trimming.
    Use this when displaying user-provided names.
    """
    if not full_name:
        return ""

    # Escape HTML entities
    sanitized = html.escape(full_name.strip())

    # Limit length
    return sanitized[:MAX_FULL_NAME_LENGTH]


# ruff: noqa: PLR0911
def association(request):
    """
    The association view
    :param request: the request
    """

    # first, see whether we have an unassociated user
    userinfo_is_valid: bool
    userinfo: dict | None
    userinfo_is_valid, userinfo = get_secure_userinfo(request)

    # if the userinfo is not valid, redirect to login
    if not userinfo_is_valid:
        return redirect(reverse("login"))

    # check the user is not properly logged in and redirect if so
    user = request.user
    if user and user.is_authenticated:
        return redirect(reverse("my_profile"))

    context = {
        "cilogon_sub": userinfo.get("sub", ""),
        "open_networks": settings.OPEN_REGISTRATION_NETWORKS,
    }

    # Check that we have a valid cilogon_sub before proceeding
    if not context["cilogon_sub"]:
        logger.error("The sub was not passed to the association view")
        return render(request, "cilogon/registration_error.html")

    # Load terms of service content for the registration form
    terms_page = SitePage.objects.filter(slug="terms-of-service").first()
    if terms_page:
        context["terms_content"] = terms_page.body
        context["terms_title"] = terms_page.title

    # check if we have an email POSTed
    if request.method == "POST":
        email = request.POST.get("email")
        if email:
            # search for a Profile with this email
            profile = Profile.objects.filter(email=email).first()

            # if we have a profile, generate a UUID4
            if profile:
                associate_with_existing_profile(
                    email, profile, request, userinfo
                )
                # render to the confirm page
                return redirect(reverse("confirm"))
            # check for other emails
            profile = Profile.objects.filter(emails__contains=[email]).first()

            # if we have a profile, generate a UUID4
            if profile:
                associate_with_existing_profile(
                    email, profile, request, userinfo
                )
                # render to the confirm page
                return redirect(reverse("confirm"))

            # if we get here, this is a new user
            msg = f"Could not find a profile with that email {email}"
            logger.info(msg)

            context.update({"error": "No profile found with that email"})
            context.update(
                {
                    "email": userinfo.get("email", ""),
                    "first_name": userinfo.get("given_name", ""),
                    "last_name": userinfo.get("family_name", ""),
                    "userinfo": userinfo,
                }
            )

        return render(request, "cilogon/new_user.html", context)

    return render(request, "cilogon/association.html", context)


def send_new_email_verify(email, profile, request):
    uuid = uuid4().hex

    # create a new EmailVerification entry
    email_verification = EmailVerification.objects.create(
        secret_uuid=uuid,
        profile=profile,
        sub=email,
    )

    # replace the email for testing purposes
    email = sanitize_email_for_dev(email)

    # send an email
    send_knowledge_commons_email(
        recipient_email=email,
        context_data={
            "uuid": uuid,
            "request": request,
        },
        template_file="mail/add_new_email.html",
    )

    # delete any expired existing EmailVerification entries
    EmailVerification.garbage_collect()


def send_registration_verification_email(email, profile, cilogon_sub, request):
    """
    Send a verification email for new user registration.

    The user must click the link to verify their email before they can log in.
    This creates an EmailVerification with the cilogon sub, which will be used
    to create the SubAssociation when they click the link.
    """

    uuid = uuid4().hex

    # create a new EmailVerification entry
    email_verification = EmailVerification.objects.create(
        secret_uuid=uuid,
        profile=profile,
        sub=cilogon_sub,
    )

    # replace the email for testing purposes
    email = sanitize_email_for_dev(email)

    # send an email
    send_knowledge_commons_email(
        recipient_email=email,
        context_data={
            "uuid": uuid,
            "request": request,
            "username": profile.username,
        },
        template_file="mail/verify_registration.html",
    )

    # delete any expired existing EmailVerification entries
    EmailVerification.garbage_collect()


def associate_with_existing_profile(email, profile, request, userinfo):
    uuid = uuid4().hex

    # create a new EmailVerification entry
    email_verification = EmailVerification.objects.create(
        secret_uuid=uuid,
        profile=profile,
        sub=userinfo.get("sub", ""),
    )

    # replace the email for testing purposes
    email = sanitize_email_for_dev(email)

    # send an email
    send_knowledge_commons_email(
        recipient_email=email,
        context_data={
            "uuid": uuid,
            "request": request,
        },
        template_file="mail/associate.html",
    )

    # delete any expired existing EmailVerification entries
    EmailVerification.garbage_collect()


def user_updated(request):
    """
    A view that simulates the remote webhook for local testing purposes
    :param request: the request
    """
    return JsonResponse({"status": "OK"}, status=200)


def confirm(request):
    """
    The confirmation of email view
    :param request: the request
    """
    return render(request, "cilogon/confirm.html", {})


def activate(request, secret_key: str):
    """
    The activation view clicked by a user from email.

    This handles both:
    1. New user registration verification (first SubAssociation for profile)
    2. Existing user adding a new login method (additional SubAssociation)
    """

    EmailVerification.garbage_collect()

    # get the verification by secret key or 404
    verify: EmailVerification = get_object_or_404(
        EmailVerification, secret_uuid=secret_key
    )

    # check that this hasn't expired
    if verify.is_expired():
        verify.delete()
        messages.error(
            request,
            "This verification link has expired. Please request a new one.",
        )
        return redirect(reverse("login"))

    # Save references before deleting the verification
    profile = verify.profile
    sub = verify.sub

    # Check if this is a new registration (no existing SubAssociations)
    is_new_registration = not SubAssociation.objects.filter(
        profile=profile
    ).exists()

    # create a sub association
    SubAssociation.objects.create(
        sub=sub,
        profile=profile,
    )

    # delete the verification as it's no longer needed
    verify.delete()

    # send a message to the webhooks
    send_association_message(sub=sub, kc_id=profile.username)

    # For new registrations, run the post-registration tasks
    if is_new_registration:
        # Add the user to Mailchimp
        hcommons_add_new_user_to_mailchimp(profile.username)

        # Send webhooks to other services
        ExternalSync.sync(profile=profile, send_webhook=True)

    # Log the user in so they don't have to go through OAuth again
    try:
        user = User.objects.get(username=profile.username)
        login(request, user)
    except User.DoesNotExist:
        # User doesn't exist yet (shouldn't happen for new registrations
        # since we create it, but could happen for legacy associations)
        logger.warning(
            "User %s does not exist during activation",
            profile.username,
        )

    # redirect the user to their Profile page
    return redirect(reverse("my_profile"))


@require_http_methods(["GET", "POST"])
@transaction.atomic
@staff_member_required
def upload_csv_view(request):
    """
    Handles CSV upload, processes it in-memory with csv.DictReader,
    and renders a summary page.
    """
    society = "SAH"

    if request.method == "POST":
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]

            # Read and decode the file into text
            # utf-8-sig handles BOM if present
            decoded = csv_file.read().decode("utf-8-sig")
            io_string = io.StringIO(decoded)

            reader = csv.DictReader(io_string)

            # first, iterate over all users with SAH in role_overrides
            users = Profile.objects.filter(role_overrides__contains=[society])

            output = []

            # temporarily remove flag from all users
            for user in users:
                user.role_overrides.remove(society)
                user.save()

                msg = f"Removed {society} from {user.username}"
                output.append(msg)
                logger.info(msg)

            processed_rows: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []

            # now re-add the flag if in the spreadsheet
            # ruff: noqa: BLE001
            for _, row in enumerate(reader, start=2):  # line 1 is header

                email = row.get("Email", None)

                if email:
                    try:
                        user = Profile.objects.get(email=email)
                    except Profile.DoesNotExist:
                        user = Profile.objects.filter(
                            emails__contains=[email]
                        ).first()

                        if not user:
                            msg = f"Profile for {email} does not exist"
                            output.append(msg)
                            logger.info(msg)
                            errors.append({"error": msg})
                            continue

                    # if here, user should be set
                    # Only add if not already present (avoid duplicates)
                    if society not in user.role_overrides:
                        user.role_overrides.append(society)
                        user.save()

                    msg = f"Added {society} to {user.username}"
                    output.append(msg)
                    logger.info(msg)

                processed_rows.append(row)

            headers = reader.fieldnames or []

            context = {
                "headers": headers,
                "preview_rows": processed_rows[:20],  # show first 20
                "total_rows": len(processed_rows),
                "error_count": len(errors),
                "errors": errors[:20],  # preview first 20 errors
                "output": output,
            }
            return render(request, "csv_import/result.html", context)
    else:
        form = UploadCSVForm()

    return render(request, "csv_import/upload.html", {"form": form})
