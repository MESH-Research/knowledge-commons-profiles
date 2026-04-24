"""
View for uploading CV files via AJAX (issue #453).

Allows users to upload a CV file immediately on selection,
without needing to click Save on the entire profile form.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from knowledge_commons_profiles.newprofile.forms import CvUploadForm
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


@login_required
@require_POST
def upload_cv(request, username=None):
    if username is None:
        username = request.user.username
    elif not request.user.is_staff and username != request.user.username:
        return JsonResponse(
            {"ok": False, "error": "Permission denied."}, status=403
        )

    form = CvUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = "; ".join(
            e for field_errors in form.errors.values() for e in field_errors
        )
        return JsonResponse(
            {"ok": False, "error": errors or "Invalid file."}, status=400
        )

    cv_file = form.cleaned_data["cv_file"]

    profile = Profile.objects.get(username=username)

    # Save the file to the profile — the pre_save signal in signals.py
    # will automatically delete the old CV file if one exists
    profile.cv_file = cv_file
    profile.save(update_fields=["cv_file"])

    url = profile.cv_file.url if profile.cv_file else ""
    filename = profile.cv_file.name if profile.cv_file else ""

    msg = f"Uploaded CV for {username}: {filename}"
    logger.info(msg)

    return JsonResponse(
        {"ok": True, "url": url, "filename": filename}
    )


@login_required
@require_POST
def delete_cv(request, username=None):
    if username is None:
        username = request.user.username
    elif not request.user.is_staff and username != request.user.username:
        return JsonResponse(
            {"ok": False, "error": "Permission denied."}, status=403
        )

    profile = Profile.objects.get(username=username)

    # Clearing cv_file triggers the pre_save signal in signals.py, which
    # deletes the old file from storage (S3 in production).
    if profile.cv_file:
        filename = profile.cv_file.name
        profile.cv_file = None
        profile.save(update_fields=["cv_file"])
        msg = f"Deleted CV for {username}: {filename}"
        logger.info(msg)

    return JsonResponse({"ok": True})
