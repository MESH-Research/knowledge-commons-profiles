"""
Views for CILogon

"""

import logging
from enum import IntEnum
from uuid import uuid4

import requests
import sentry_sdk
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.models import TokenUserAgentAssociations
from knowledge_commons_profiles.cilogon.oauth import ORCIDHandledToken
from knowledge_commons_profiles.cilogon.oauth import delete_associations
from knowledge_commons_profiles.cilogon.oauth import find_user_and_login
from knowledge_commons_profiles.cilogon.oauth import forward_url
from knowledge_commons_profiles.cilogon.oauth import get_secure_userinfo
from knowledge_commons_profiles.cilogon.oauth import oauth
from knowledge_commons_profiles.cilogon.oauth import pack_state
from knowledge_commons_profiles.cilogon.oauth import revoke_token
from knowledge_commons_profiles.cilogon.oauth import send_association_message
from knowledge_commons_profiles.cilogon.oauth import store_session_variables
from knowledge_commons_profiles.common.profiles_email import (
    sanitize_email_for_dev,
)
from knowledge_commons_profiles.common.profiles_email import (
    send_knowledge_commons_email,
)
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.rest_api.sync import ExternalSync

logger = logging.getLogger(__name__)


class RedirectBehaviour(IntEnum):
    """
    Enum for redirect behaviour
    """

    REDIRECT = 1
    NO_REDIRECT = 2


def cilogon_login(request):
    """
    The login redirect for OAuth
    :param request: the request
    """
    # flush the session
    app_logout(request, redirect_behaviour=RedirectBehaviour.NO_REDIRECT)
    request.session.flush()

    # can use this to pass a next_url if we wish
    # an empty string assumes authentication to Profiles app
    # values for base domain here must be present in
    # settings.ALLOWED_CILOGON_FORWARDING_DOMAINS
    state = pack_state("")

    # we need to redirect to https here because the load balancer operates
    # behind the scenes on http, which is not the external URL we want
    redirect_uri = request.build_absolute_uri(
        "/" + settings.OIDC_CALLBACK
    ).replace("http://", "https://")

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
        # yes, found a sub->profile, log them in
        find_user_and_login(request, sub_association)

        # update user network affiliations
        ExternalSync.sync(profile=sub_association.profile)

        # return to the profile page
        return redirect(reverse("my_profile"))

    # no, no user. Redirect to the profile association page
    return redirect(reverse("associate"))


def app_logout(
    request,
    redirect_behaviour: RedirectBehaviour = RedirectBehaviour.REDIRECT,
    user_name=None,
    user_agent=None,
    apps=None,
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
    logout(request)

    if redirect_behaviour == RedirectBehaviour.REDIRECT:
        # redirect the user to the home page
        # TODO: proper redirect
        return redirect("/")

    return None


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

    if request.method == "POST":
        email, full_name, username = extract_form_data(
            context, request, userinfo
        )

        errored = False
        errored = validate_form(email, full_name, request, username)

        if errored:
            return render(request, "cilogon/new_user.html", context)

        # Create the Profile object
        profile = Profile.objects.create(
            name=full_name, username=username, email=email
        )

        # Create the corresponding Django User
        user = User.objects.create(username=username, email=email)

        # Log the user in
        login(request, user)

        # Create the SubAssociation with the cilogon sub
        SubAssociation.objects.create(
            sub=context["cilogon_sub"], profile=profile
        )

        # Redirect to my_profile page
        return redirect(reverse("my_profile"))

    return render(request, "cilogon/new_user.html", context)


def extract_form_data(context, request, userinfo):
    # get the form data
    email = request.POST.get("email", None)
    username = request.POST.get("username", None)
    full_name = request.POST.get("full_name", None)
    try:
        first_name = full_name.split(" ")[0]
        last_name = " ".join(full_name.split(" ")[1:])
    except IndexError:
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
    # TODO: SECURITY BUG - Missing username uniqueness validation
    # Should check if username already exists before attempting
    # User.objects.create()
    # See docs/cilogon_security_issues.md for details

    errored = False

    # check none of these are blank
    if not email or not username or not full_name:
        errored = True
        messages.error(request, "Please fill in all fields")
    # check whether this email already exists
    profile = Profile.objects.filter(email=email).first()
    if profile:
        errored = True
        messages.error(request, "This email already exists")
    # check whether this username already exists
    profile = Profile.objects.filter(username=username).first()
    if profile:
        errored = True
        messages.error(request, "This username already exists")
    return errored


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

    context = {"cilogon_sub": userinfo.get("sub", "")}

    # Check that we have a valid cilogon_sub before proceeding
    if not context["cilogon_sub"]:
        logger.error("The sub was not passed to the association view")
        return render(request, "cilogon/registration_error.html")

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
            context.update({"error": "No profile found with that email"})
        else:
            # if we get here, this is a new user
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


def associate_with_existing_profile(email, profile, request, userinfo):
    uuid = uuid4().hex
    # delete any existing EmailVerification entries
    EmailVerification.objects.filter(profile=profile).delete()
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
            "verification_id": email_verification.id,
            "request": request,
        },
        template_file="mail/associate.html",
    )


def confirm(request):
    """
    The confirmation of email view
    :param request: the request
    """
    return render(request, "cilogon/confirm.html", {})


def activate(request, verification_id: int, secret_key: str):
    """
    The activation view clicked by a user from email
    """

    # get the verification and secret key or 404
    verify: EmailVerification = get_object_or_404(
        EmailVerification, secret_uuid=secret_key, id=verification_id
    )

    # create a sub association
    SubAssociation.objects.create(
        sub=verify.sub,
        profile=verify.profile,
    )

    # delete the verification as it's no longer needed
    verify.delete()

    # send a message to the webhooks
    send_association_message(sub=verify.sub, kc_id=verify.profile.username)

    # redirect the user to their Profile page
    return redirect(reverse("my_profile"))
