"""
A class of API calls for user details
"""

from django.db.models import F

from newprofile import mastodon
from newprofile.models import Profile
from newprofile.works import WorksDeposits


class API:
    """
    A class containing API calls for user details
    """

    def __init__(self, request, user):
        """
        Initialise the API class with a request and user object.

        Args:
            request: The request object.
            user: The user object.
        """
        self.request = request
        self.user = user
        self.profile = Profile.objects.prefetch_related(
            "academic_interests"
        ).get(username=user)

        self.profile_info = {}

        self.get_profile_info()

        self.mastodon_profile = self.profile_info["mastodon"]

        if self.mastodon_profile:
            self.mastodon_username, self.mastodon_server = (
                self.mastodon_profile.split("@")[0],
                self.mastodon_profile.split("@")[1],
            )
            self.mastodon_posts = mastodon.MastodonFeed(
                self.mastodon_username, self.mastodon_server
            )

        self.works_deposits = WorksDeposits(
            self.profile_info["username"], "https://works.hcommons.org"
        )

        self.works_html = self.works_deposits.display_filter()

    def get_profile_info(self):
        """
        Returns a dictionary containing profile information about the user.

        Returns:
            A dictionary containing profile information.
        """

        # A dictionary containing profile information
        self.profile_info = {
            "name": self.profile.name,
            "username": self.profile.username,
            "title": self.profile.title,
            "affiliation": self.profile.affiliation,
            "twitter": self.profile.twitter,
            "github": self.profile.github,
            "email": self.profile.email,
            "orcid": self.profile.orcid,
            "mastodon": self.profile.mastodon,
            "profile_image": self.profile.profile_image,
            "works_username": self.profile.works_username,
        }

        return self.profile_info

    def get_academic_interests(self):
        """
        Returns a list of academic interests for a user.

        This endpoint can be used to retrieve a list of academic interests
        that the specified user has.

        Returns:
            A list of academic interests.
        """

        # A list of academic interests
        return self.profile.academic_interests.all()

    def get_about_user(self):
        """
        Returns a string about the specified user.

        This endpoint can be used to retrieve a string about the specified user.

        Returns:
            A string about the user.
        """
        # A string about the user
        return self.profile.about_user

    def get_education(self):
        """
        Return a string of the user's education details.

        Returns:
            A string of the user's education details.
        """
        return self.profile.education
