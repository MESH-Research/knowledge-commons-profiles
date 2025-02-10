"""
A management command to import profile images from directory structure
"""

import os

import rich
from django.core.management.base import BaseCommand
from rich.progress import track

from newprofile.models import (
    CoverImage,
    WpUser,
    Profile,
    ProfileImage,
)


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

    def handle(self, *args, **options):
        """
        Handle the command
        :return:
        """
        base_path = options["base_dir"]
        avatars_path = os.path.join(base_path, "avatars")

        # Ensure the members directory exists
        if not os.path.exists(avatars_path):
            self.stdout.write(
                self.style.ERROR(f"Directory not found: {avatars_path}")
            )
            return

        # Walk through member directories
        for user_id in track(os.listdir(avatars_path)):
            if not user_id.isdigit():
                continue

            avatars_image_path = os.path.join(avatars_path, user_id)
            if not os.path.exists(avatars_image_path):
                continue

            thumb = None
            full = None

            # Look for image files in the cover-image directory
            for filename in os.listdir(avatars_image_path):
                if filename.endswith(
                    ("bpthumb.jpg", "bpthumb.jpeg", "bpthumb.png")
                ):
                    thumb = filename

                if filename.endswith(
                    ("bpfull.jpg", "bpfull.jpeg", "bpfull.png")
                ):
                    full = filename

            if not thumb and not full:
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
                    username=username
                ).first()

                if not profile_object:
                    rich.print(f"Profile for {user_id} not found, skipping")
                    continue

                final_full_filename = f"https://hcommons.org/app/uploads/avatars/{user_id}/{full}"
                final_thumb_filename = f"https://hcommons.org/app/uploads/avatars/{user_id}/{thumb}"

                profile_image, created = ProfileImage.objects.update_or_create(
                    profile=profile_object,
                    defaults={
                        "thumb": final_thumb_filename,
                        "full": final_full_filename,
                    },
                )

                status = "Created" if created else "Updated"
                rich.print(
                    f"{status} profile image for user {user_id}: {filename}"
                )

                print(profile_image)

            except Exception as e:
                rich.print(f"Error processing user {user_id}: {str(e)}")

        rich.print("Import completed")
