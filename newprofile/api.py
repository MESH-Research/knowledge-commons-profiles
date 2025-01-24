"""
A class of API calls for user details
"""

from django.db import connections

from newprofile import mastodon
from newprofile.models import Profile, WpUser, WpBlog, WpPostSubTable
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
        self.wp_user = WpUser.objects.get(user_login=user)

        self.profile_info = {}

        self.get_profile_info()

        self.mastodon_profile = self.profile_info["mastodon"]

        if self.mastodon_profile:
            self.mastodon_username, self.mastodon_server = (
                self.mastodon_profile[1:].split("@")[0],
                "hcommons.social",
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

    def get_blog_posts(self):
        """
        Get blog posts from the Wordpress database
        :return:
        """
        # first get a list of tables in the database
        with connections["wordpress_dev"].cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            row = [row[0] for row in cursor.fetchall()]

        # get a full list of blogs
        blog_ids = WpBlog.objects.values_list("blog_id", flat=True)

        # build a massive SQL query string that joins all these tables together
        select_statements = []

        for num in blog_ids:
            if f"wp_{num}_posts" in row:
                select_stmt = f"""
                    SELECT 
                    {num} as blog_id,
                    p.ID,
                    p.post_author,
                    p.post_date,
                    p.post_date_gmt,
                    p.post_title COLLATE utf8mb4_unicode_ci as post_title,
                    p.post_status COLLATE utf8mb4_unicode_ci as post_status,
                    p.post_name COLLATE utf8mb4_unicode_ci as post_name,
                    p.post_modified,
                    p.post_modified_gmt,
                    p.post_type COLLATE utf8mb4_unicode_ci as post_type,
                    o.option_value COLLATE utf8mb4_unicode_ci as blogname
                    FROM wp_{num}_posts p
                    LEFT JOIN wp_{num}_options o ON o.option_name = 'blogname'
                    WHERE p.post_author = {self.wp_user.id} AND p.post_status='publish' AND p.post_type='post'
                """
                select_statements.append(select_stmt)

        # Combine all SELECT statements with UNION ALL
        final_query = "\nUNION ALL\n".join(select_statements)

        final_query = f"""
                    WITH unified_posts AS (
                        {final_query}
                    )
                    SELECT *
                    FROM unified_posts
                    ORDER BY post_date DESC
                    LIMIT 25
                """

        results = []

        for item in WpPostSubTable.objects.raw(final_query):
            results.append(item)

        return results

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
