"""
A management command to import profile images from directory structure
"""

from pathlib import Path

import rich
from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import ProfileImage
from knowledge_commons_profiles.newprofile.models import WpUser


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Import profile images from directory structure into database"

    def add_arguments(self, parser):
        """
        Add arguments to the command
        """
        parser.add_argument(
            "base_dir",
            type=str,
            help="Base directory containing members folder",
        )

    def handle(self, *args, **options):  # noqa: C901
        """
        Handle the command
        :return:
        """
        base_path = options["base_dir"]
        avatars_path = Path(base_path) / "avatars"

        # Ensure the members directory exists
        if not Path.exists(avatars_path):
            rich.print(f"Directory not found: {avatars_path!s}")
            return

        # Walk through member directories
        for user_id_full in track(avatars_path.iterdir()):
            # get the last folder part here (e.g. /a/b/c -> c)
            user_id = user_id_full.stem

            if not str(user_id).isdigit():
                rich.print(f"Skipping {user_id!s} (not a number)")
                continue

            avatars_image_path = Path(avatars_path) / user_id
            if not avatars_image_path.exists():
                rich.print(f"Skipping {avatars_image_path!s}")
                continue

            thumb = None
            full = None

            # Look for image files in the cover-image directory
            for filename in avatars_image_path.iterdir():
                filename_plain = filename.name

                if str(filename_plain).endswith(
                    ("bpthumb.jpg", "bpthumb.jpeg", "bpthumb.png"),
                ):
                    thumb = filename_plain

                if str(filename_plain).endswith(
                    ("bpfull.jpg", "bpfull.jpeg", "bpfull.png"),
                ):
                    full = filename_plain

            if not thumb and not full:
                rich.print(f"No image files found: {avatars_image_path!s}")
                continue

            try:
                # Get or create user instance
                user = WpUser.objects.filter(id=user_id).first()

                if not user:
                    rich.print(f"User {user_id} not found, skipping")
                    continue

                # Create or update cover image record
                username = user.user_login

                profile_object = Profile.objects.filter(
                    username=username,
                ).first()

                if not profile_object:
                    rich.print(f"Profile for {user_id} not found, skipping")
                    continue

                final_full_filename = (
                    f"https://hcommons.org/app/uploads"
                    f"/avatars/{user_id}/{full}"
                )
                final_thumb_filename = (
                    f"https://hcommons.org/app/uploads"
                    f"/avatars/{user_id}/{thumb}"
                )

                profile_image, created = ProfileImage.objects.update_or_create(
                    profile=profile_object,
                    defaults={
                        "thumb": final_thumb_filename,
                        "full": final_full_filename,
                    },
                )

                status = "Created" if created else "Updated"
                rich.print(
                    f"{status} profile image for user {user_id}: "
                    f"{filename_plain}",
                )

                rich.print(profile_image)

            except Exception as e:  # noqa: BLE001
                rich.print(f"Error processing user {user_id}: {e!s}")

        rich.print("Import completed")
