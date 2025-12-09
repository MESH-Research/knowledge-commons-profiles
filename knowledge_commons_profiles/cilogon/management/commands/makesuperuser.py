"""
A management command to toggle superuser status for a user
"""


import rich
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Command to toggle superuser status for a user
    """

    help = "Toggle superuser status for a user"

    def add_arguments(self, parser):
        """
        Add arguments to the command
        """
        parser.add_argument(
            "username",
            type=str,
            help="The username to toggle",
        )

    def handle(self, *args, **options):
        """
        Handle the command
        :return:
        """
        username = options["username"]

        user: User = User.objects.filter(username=username).first()

        if not user:
            rich.print(f"User {username} not found")
            return

        user.is_superuser = not user.is_superuser
        user.is_staff = not user.is_staff
        user.save()

        rich.print(
            f"Superuser status for {username} set to {user.is_superuser}"
        )
        rich.print(f"Staff status for {username} set to {user.is_staff}")
        rich.print(
            f"Therefore, superadmin status for {username} is "
            f"{any([user.is_superuser, user.is_staff])}"
        )
