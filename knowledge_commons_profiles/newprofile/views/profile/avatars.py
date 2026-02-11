# views.py
import io
import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

from knowledge_commons_profiles.newprofile.cc_search import (
    index_profile_in_cc_search,
)
from knowledge_commons_profiles.newprofile.forms import AvatarUploadForm
from knowledge_commons_profiles.newprofile.models import CoverImage
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


@login_required
@require_POST
def upload_avatar(request, username=None):
    if username is None:
        username = request.user.username
    elif not request.user.is_staff and username != request.user.username:
        raise PermissionDenied

    form = AvatarUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid form data.")

    img_file = form.cleaned_data["image"]

    # Pillow verification & basic content-type allowlist
    # ruff: noqa: BLE001
    try:
        im = Image.open(img_file)
        im.verify()  # ensures it's really an image
    except Exception:
        msg = "Corrupt or unsupported image"
        logger.exception(msg)
        return HttpResponseBadRequest(msg)
    img_file.seek(0)
    im = Image.open(img_file).convert(
        "RGB"
    )  # strip alpha/exif, normalize mode

    # Disallow SVG and super-huge images
    if getattr(img_file, "content_type", "") not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        msg = "Only JPEG/PNG/WebP are allowed."
        logger.exception(msg)
        return HttpResponseBadRequest(msg)
    if max(im.size) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        msg = "Image too large."
        logger.exception(msg)
        return HttpResponseBadRequest(msg)

    # Resize to exactly 150x150 (high-quality)
    im = im.resize((150, 150), resample=Image.Resampling.LANCZOS)

    # Re-encode to JPEG
    out = compress_image(im)

    # Save with a safe randomized name
    url = save_image(out, request, "profile_images")

    # Save to user's profile (authorization: user owns this profile)
    profile = Profile.objects.get(username=username)
    profile.profile_image = url
    profile.save(update_fields=["profile_image"])

    msg = f"Saved avatar for {username} to {url}"
    logger.info(msg)

    # now send an update to the CC search client because avatar has changed
    index_profile_in_cc_search(profile)

    return JsonResponse({"ok": True, "url": url})


def save_image(out, request, prefix) -> str:
    filename = f"{prefix}/{uuid.uuid4().hex}.jpg"
    default_storage.save(filename, ContentFile(out.getvalue()))

    url = default_storage.url(filename)  # like /media/profile_images/abc.jpg
    msg = f"Uploaded image for {request.user.username} to {url}"
    logger.info(msg)
    return url


@login_required
@require_POST
def upload_cover(request, username=None):
    if username is None:
        username = request.user.username
    elif not request.user.is_staff and username != request.user.username:
        raise PermissionDenied

    form = AvatarUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid form data.")

    img_file = form.cleaned_data["image"]

    # Pillow verification & basic content-type allowlist
    # ruff: noqa: BLE001
    try:
        im = Image.open(img_file)
        im.verify()  # ensures it's really an image
    except Exception:
        msg = "Corrupt or unsupported image"
        logger.exception(msg)
        return HttpResponseBadRequest(msg)
    img_file.seek(0)
    im = Image.open(img_file).convert(
        "RGB"
    )  # strip alpha/exif, normalize mode

    # Disallow SVG and super-huge images
    if getattr(img_file, "content_type", "") not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        msg = "Only JPEG/PNG/WebP are allowed."
        logger.exception(msg)
        return HttpResponseBadRequest(msg)
    if max(im.size) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        msg = "Image too large."
        logger.exception(msg)
        return HttpResponseBadRequest(msg)

    # Resize to exactly 1480x200 (high-quality)
    im = im.resize((1480, 200), resample=Image.Resampling.LANCZOS)

    # Re-encode to JPEG
    out = compress_image(im)

    # Save with a safe randomized name
    url = save_image(out, request, "cover_images")

    # Save to user's profile (authorization: user owns this profile)
    profile = Profile.objects.get(username=username)

    # delete all existing cover images (in a model called CoverImage)
    CoverImage.objects.filter(profile=profile).delete()

    # add a new CoverImage
    cover_image = CoverImage.objects.create(
        profile=profile, filename=url, file_path=url
    )
    cover_image.save()

    msg = f"Saved cover for {username} to {url}"
    logger.info(msg)

    return JsonResponse({"ok": True, "url": url})


def compress_image(im) -> io.BytesIO:
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=90, optimize=True)
    out.seek(0)
    return out
