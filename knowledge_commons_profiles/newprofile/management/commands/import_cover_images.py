"""
A management command to import cover images from directory structure
"""

from pathlib import Path

import rich
from django.core.management.base import BaseCommand
from rich.progress import track

from knowledge_commons_profiles.newprofile.models import CoverImage
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpUser


class Command(BaseCommand):
    """
    Command to import cover images from directory structure
    """

    help = "Import cover images from directory structure into database"

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
        members_path = Path(base_path / "members")

        # Ensure the members directory exists
        if not Path.exists(members_path):
            self.stdout.write(
                self.style.ERROR(f"Directory not found: {members_path!s}"),
            )
            return

        # Walk through member directories
        for user_id in track(members_path.iterdir()):
            if not user_id.isdigit():
                continue

            cover_image_path = Path(
                members_path / user_id / "cover-image",
            )
            if not Path.exists(cover_image_path):
                continue

            # Look for image files in the cover-image directory
            for filename in cover_image_path.iterdir():
                if filename.endswith((".jpg", ".jpeg", ".png")):
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
                            rich.print(
                                f"Profile for {user_id} not found, skipping",
                            )
                            continue

                        final_filename = f"https://hcommons.org/app/uploads/buddypress/members/{user_id}/cover-image/{filename}"

                        cover_image, created = (
                            CoverImage.objects.update_or_create(
                                profile=profile_object,
                                defaults={
                                    "filename": filename,
                                    "file_path": final_filename,
                                },
                            )
                        )

                        status = "Created" if created else "Updated"
                        rich.print(
                            f"{status} cover image for user {user_id}: "
                            f"{filename}",
                        )

                    except Exception as e:  # noqa: BLE001
                        rich.print(
                            f"Error processing user {user_id}: {e!s}",
                        )

        rich.print("Import completed")
