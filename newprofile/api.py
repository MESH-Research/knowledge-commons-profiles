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

    def __init__(self, request, user, use_wordpress=True):
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

    def update_profile(self, data):
        """
        Update the user's profile information.
        """

        # TODO: permissions/SAML login

        """
        {'profile_info': {'name': 'Kathleen Fitzpatrick Again', 'username': 'kfitz', 'title': 'Interim Associate Dean for Research and Graduate Studies', 'affiliation': '', 'twitter': '', 'github': '', 'email': 'kfitz@msu.edu', 'orcid': '0000-0002-5251-0307', 'mastodon': '@kfitz@hcommons.social', 'profile_image': '', 'works_username': ''}, 'academic_interests': [], 'education': 'PhD, English, <a href="https://commons.mla.org/members/?s=New+York+University" rel="nofollow">New York University</a>, 1998.\r\nMFA, English, <a href="https://commons.mla.org/members/?s=Louisiana+State+University" rel="nofollow">Louisiana State University</a>, 1991.\r\nBA, English, <a href="https://commons.mla.org/members/?s=Louisiana+State+University" rel="nofollow">Louisiana State University</a>, 1988.', 'about_user': 'Kathleen Fitzpatrick is Interim Associate Dean for Research and Graduate Studies in the College of Arts and Letters at Michigan State University, where she also holds an appointment as Professor of English. She is founder of <a href="https://meshresearch.net" rel="nofollow">MESH</a>, a research and development unit focused on the future of scholarly communication, for which she served as director between 2020 and 2024. She is project director of Knowledge Commons, an open-access, open-source network serving more than 40,000 scholars and practitioners across the disciplines and around the world. She is author of four books, the most recent of which, <a href="https://www.press.jhu.edu/books/title/12787/leading-generously" rel="nofollow"><em>Leading Generously: Tools for Transformation</em></a>, is forthcoming from Johns Hopkins University Press in fall 2024. She is president of the board of directors of the <a href="https://educopia.org" rel="nofollow">Educopia Institute</a>, and she served as president of the <a href="https://ach.org" rel="nofollow">Association for Computers and the Humanities</a> from 2020 to 2022.\r\n\r\nYou can also find me on <a href="https://hcommons.social/@kfitz" rel="me nofollow">hcommons.social</a>.'}
        """

        self.profile.name = data.get("profile_info", {}).get(
            "name", self.profile.name
        )
        self.profile.title = data.get("profile_info", {}).get(
            "title", self.profile.title
        )
        self.profile.affiliation = data.get("profile_info", {}).get(
            "affiliation", self.profile.affiliation
        )
        self.profile.twitter = data.get("profile_info", {}).get(
            "twitter", self.profile.twitter
        )
        self.profile.github = data.get("profile_info", {}).get(
            "github", self.profile.github
        )
        self.profile.email = data.get("profile_info", {}).get(
            "email", self.profile.email
        )
        self.profile.orcid = data.get("profile_info", {}).get(
            "orcid", self.profile.orcid
        )
        self.profile.mastodon = data.get("profile_info", {}).get(
            "mastodon", self.profile.mastodon
        )
        self.profile.profile_image = data.get("profile_info", {}).get(
            "profile_image", self.profile.profile_image
        )
        self.profile.works_username = data.get("profile_info", {}).get(
            "works_username", self.profile.works_username
        )
        self.profile.about_user = data.get(
            "about_user", self.profile.about_user
        )
        self.profile.education = data.get("education", self.profile.education)

        self.profile.academic_interests.clear()

        for interest in data.get("academic_interests", []):
            self.profile.academic_interests.add(interest)

        for interest in data.get("academic_interests", []):
            self.profile.academic_interests.add(interest)

        self.profile.save()
