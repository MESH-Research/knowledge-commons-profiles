# views.py
import io
import logging
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Extract data from a CSV of all users"

    def handle(self, *args, **options):
        # Re-encode to JPEG
        out = io.BytesIO()
        out.write(b"hello")
        out.seek(0)

        # Save with a safe randomized name
        filename = f"profile_images/{uuid.uuid4().hex}.txt"
        default_storage.save(filename, ContentFile(out.getvalue()))

        url = default_storage.url(
            filename
        )  # like /media/profile_images/abc.jpg
        msg = f"Uploaded avatar to {url}"
        logger.info(msg)
