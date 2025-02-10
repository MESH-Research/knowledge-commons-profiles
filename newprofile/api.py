"""
A class of API calls for user details
"""

from django.db import connections
from django.http import Http404

from newprofile import mastodon
from newprofile.models import (
    Profile,
    WpUser,
    WpBlog,
    WpPostSubTable,
    WpBpGroupMember,
)
from newprofile.works import WorksDeposits
from django.contrib.auth import (
    get_user_model,
    login,
)
from django.db import connections

User = get_user_model()


class API:
    """
    A class containing API calls for user details
    """

    def __init__(self, request, user, use_wordpress=True, create=False):
        """
        Initialise the API class with a request and user object.
        """
        self.request = request
        self.user = user
        try:
            self.profile = Profile.objects.prefetch_related(
                "academic_interests"
            ).get(username=user)
        except Profile.DoesNotExist as exc:
            if create:
                self.profile = Profile.objects.create(
                    username=user, email=email
                )
            else:
                # if the user exists but the Profile doesn't, then create it
                try:
                    user_object = User.objects.get(username=user)
                    self.profile = Profile.objects.create(
                        username=user, email=user_object.email
                    )
                except User.DoesNotExist as exc:
                    # raise 404
                    raise Http404("Profile not found") from exc

        self.use_wordpress = use_wordpress

        if use_wordpress:
            self.wp_user = WpUser.objects.get(user_login=user)
        else:
            self.wp_user = None

        self.profile_info = {}

        self.get_profile_info()

        self.mastodon_profile = self.profile_info["mastodon"]

        if self.mastodon_profile:
            self.mastodon_username, self.mastodon_server = (
                self.mastodon_profile[1:].split("@")[0],
                self.mastodon_profile[1:].split("@")[1],
            )
            self.mastodon_posts = mastodon.MastodonFeed(
                self.mastodon_username, self.mastodon_server
            )

        self.works_deposits = WorksDeposits(
            self.profile_info["username"], "https://works.hcommons.org"
        )

        self.works_html = self.works_deposits.display_filter()

    def get_profile_info(self, create=False):
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
        if not self.use_wordpress:
            return []

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
                    o.option_value COLLATE utf8mb4_unicode_ci as blogname,
                    b.domain COLLATE utf8mb4_unicode_ci as blogdomain,
                    b.path COLLATE utf8mb4_unicode_ci as blogpath
                    FROM wp_{num}_posts p
                    LEFT JOIN wp_{num}_options o ON o.option_name = 'blogname'
                    LEFT JOIN wp_blogs b ON b.blog_id = {num}
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

    def get_groups(self):
        """
        Return a list of groups that the user is a member of
        :return:
        """
        groups = WpBpGroupMember.objects.filter(
            user_id=self.wp_user.id, is_confirmed=True, group__status="public"
        )

        return groups
