"""
A management command to import data from the API into the Profile model
"""

from django.core.management.base import BaseCommand

from newprofile.models import Profile, AcademicInterest
from newprofile.api import API


class Command(BaseCommand):
    help = "Import data from API into the Profile model"

    def handle(self, *args, **options):
        """
        This method imports data from the API into the Profile model
        """
        api = API(request=None, user="martin_eve")
        data = api.get_profile_info()

        # Get or create the Profile object
        profile, _ = Profile.objects.get_or_create(username=data["username"])

        # Set the fields in the Profile object
        profile.name = data["name"]
        profile.username = data["username"]
        profile.title = data["title"]
        profile.affiliation = data["affiliation"]
        profile.twitter = data["twitter"]
        profile.github = data["github"]
        profile.email = data["email"]
        profile.orcid = data["orcid"]
        profile.mastodon = data["mastodon"]
        profile.profile_image = data["profile_image"]
        profile.works_username = data["works_username"]

        # Get or create the AcademicInterest objects
        for interest in api.get_academic_interests():
            # Get or create the AcademicInterest
            new_interest, _ = AcademicInterest.objects.get_or_create(
                text=interest
            )

            # Save the AcademicInterest
            new_interest.save()

            # Add the AcademicInterest to the Profile
            profile.academic_interests.add(new_interest)

        # Get the about user and education fields
        profile.about_user = api.get_about_user()
        profile.education = api.get_education()

        # Save the Profile
        profile.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported data from API into the Profile model"
            )
        )
