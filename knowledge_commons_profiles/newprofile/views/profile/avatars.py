# views.py
import io
import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

from knowledge_commons_profiles.newprofile.forms import AvatarUploadForm
from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


@login_required
@require_POST
def upload_avatar(request):
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
        return HttpResponseBadRequest("Corrupt or unsupported image.")
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
        return HttpResponseBadRequest("Only JPEG/PNG/WebP are allowed.")
    if max(im.size) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return HttpResponseBadRequest("Image too large.")

    # Resize to exactly 150x150 (high-quality)
    im = im.resize((150, 150), resample=Image.Resampling.LANCZOS)

    # Re-encode to JPEG
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=90, optimize=True)
    out.seek(0)

    # Save with a safe randomized name
    filename = f"profile_images/{uuid.uuid4().hex}.jpg"
    fs = FileSystemStorage(
        location=str(settings.MEDIA_ROOT), base_url=settings.MEDIA_URL
    )
    fs.save(filename, out)

    url = fs.url(filename)  # like /media/profile_images/abc.jpg

    # Save to user's profile (authorization: user owns this profile)
    profile = Profile.objects.get(username=request.user.username)
    profile.profile_image = url
    profile.save(update_fields=["profile_image"])

    return JsonResponse({"ok": True, "url": url})
