"""
A class of API calls for user details
"""

import hashlib
from operator import itemgetter
from urllib.parse import urlencode

import phpserialize
from django.contrib.auth import (
    get_user_model,
)
from django.core.cache import cache
from django.db import connections
from django.http import Http404

import newprofile
from newprofile import mastodon
from newprofile.models import (
    Profile,
    WpUser,
    WpBlog,
    WpPostSubTable,
    WpBpGroupMember,
    WpUserMeta,
    WpBpFollow,
    WpBpUserBlogMeta,
    WpBpActivity,
    WpBpNotification,
)
from newprofile.works import WorksDeposits

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
                "academic_interests", "coverimage_set"
            ).get(username=user)
        except Profile.DoesNotExist as exc:
            if create:
                self.profile = Profile.objects.create(username=user)
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
            "publications": self.profile.publications,
            "projects": self.profile.projects,
            "memberships": self.profile.memberships,
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

        cache_key = f"blog_post_list-{self.user}"
        cached_response = cache.get(cache_key, version=newprofile.__version__)

        if cached_response is not None:
            return cached_response

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

        cache.set(
            cache_key, results, timeout=600, version=newprofile.__version__
        )

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
        groups = (
            WpBpGroupMember.objects.filter(
                user_id=self.wp_user.id,
                is_confirmed=True,
                group__status="public",
            )
            .prefetch_related("group")
            .order_by("group__name")
        )

        return groups

    def get_cover_image(self):
        """
        Return the path to the user's cover image
        :return: a cover image
        """
        cover = self.profile.coverimage_set.first()
        if cover:
            return cover.file_path

        result = WpUserMeta.objects.filter(meta_key="_bb_cover_photo").first()

        return phpserialize.unserialize(result.meta_value.encode())[
            b"attachment"
        ].decode("utf-8")

    def get_profile_photo(self):
        """
        Return the path to the user's profile image
        :return:
        """

        # see if we have a local entry
        profile_image = self.profile.profileimage_set.first()
        if profile_image:
            return profile_image.full

        # Fall back to Gravatar
        email = self.profile.email
        # default = "https://www.gravatar.com/avatar/ad42b9f55af0c9b73cd642b3c8b7853b?s=150&r=g&d=identicon"
        size = 150

        # Encode the email to lowercase and then to bytes
        email_encoded = email.lower().encode("utf-8")

        # Generate the SHA256 hash of the email
        email_hash = hashlib.sha256(email_encoded).hexdigest()

        # Construct the URL with encoded query parameters
        query_params = urlencode({"s": str(size)})
        return f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"

    def get_memberships(self):
        """
        Return a list of groups that the user is a member of
        :return:
        """
        cache_key = f"user_memberships-{self.user}"
        cached_response = cache.get(cache_key, version=newprofile.__version__)

        if cached_response is not None:
            return cached_response

        meta_object = WpUserMeta.objects.filter(
            meta_key="shib_ismemberof", user=self.wp_user
        ).first()

        try:
            # this is double serialized
            decoded_list = phpserialize.unserialize(
                phpserialize.unserialize(meta_object.meta_value.encode())
            )

            memberships = []

            # we're looking for things like this:
            # CO:COU:HASTAC:members:active
            for item in decoded_list:
                item = decoded_list[item].decode("utf-8")
                if item.startswith("CO:COU:") and item.endswith(
                    ":members:active"
                ):
                    society = item.split(":")[2]

                    if society != "HC":
                        memberships.append(society)

            cache.set(
                cache_key,
                memberships,
                timeout=600,
                version=newprofile.__version__,
            )

            return sorted(memberships)

        except Exception as e:
            return []

    def follower_count(self):
        """
        Return the number of followers
        :return: an integer
        """
        return WpBpFollow.objects.filter(follower=self.wp_user).count()

    def get_user_blogs(self):
        """
        Return a list of user blogs
        :return:
        """
        cache_key = f"user_blog_post_list-{self.user}"
        cached_response = cache.get(cache_key, version=newprofile.__version__)

        if cached_response is not None:
            return cached_response

        initial_sql = f"""
            SELECT DISTINCT
            b.blog_id, 
            b.domain, 
            u.user_email,
            b.public as is_public
            FROM wp_blogs b 
            JOIN wp_usermeta um ON um.meta_key = CONCAT('wp_', b.blog_id, '_capabilities') 
            JOIN wp_users u ON u.ID = um.user_id 
            JOIN wp_blogmeta bm ON bm.blog_id = b.blog_id 
            WHERE um.user_id = { self.wp_user.id }
            AND b.public = 1 
            AND b.site_id = 2 # restrict to HC
            AND um.meta_value LIKE '%administrator%' 
            GROUP BY b.domain
        """

        with connections["wordpress_dev"].cursor() as cursor:
            cursor.execute(initial_sql)
            rows = cursor.fetchall()

        results = []

        for row in rows:
            blog_meta = WpBpUserBlogMeta.objects.select_related("blog").get(
                blog_id=row[0], meta_key="name"
            )

            results.append((blog_meta.meta_value, blog_meta.blog.domain))

        cache.set(
            cache_key, results, timeout=600, version=newprofile.__version__
        )

        return sorted(results, key=itemgetter(0))

    def get_activity(self):
        """
        Return a list of user activities
        """
        cache_key = f"user_activities_list-{self.user}"
        cached_response = cache.get(cache_key, version=newprofile.__version__)

        if cached_response is not None:
            return cached_response

        activities = (
            WpBpActivity.objects.prefetch_related("meta")
            .filter(
                user_id=self.wp_user.id,
                hide_sitewide=False,
                meta__meta_key="society_id",
                meta__meta_value="hc",
            )
            .order_by("-date_recorded")
        )[:100]

        distinct_entries = []
        distinct_objects = []

        for activity in activities:
            if activity.type not in distinct_entries:
                distinct_entries.append(activity.type)
                distinct_objects.append(activity)

        cache.set(
            cache_key,
            distinct_objects[:5],
            timeout=600,
            version=newprofile.__version__,
        )

        return distinct_objects[:5]

    def get_short_notifications(self):
        """
        Return an HTML-formatted list of user notifications
        """
        if not self.use_wordpress:
            return []

        # get all new notifications for this user
        notifications_list = WpBpNotification.objects.filter(
            user_id=self.wp_user.id, is_new=True
        )

        handled_follows = False
        human_list = []
        limit = 5
        count = 0

        for notification in notifications_list:
            # followers are aggregated and counted in the dropdown
            if (
                notification.component_action == "new_follow"
                and handled_follows is False
            ):
                result = notification.get_short_string(
                    username=self.wp_user.user_login
                )

                if result:
                    human_list.append(result)

                handled_follows = True
                count += 1
            elif (
                notification.component_action == "new_follow"
                and handled_follows is True
            ):
                continue
            else:
                count += 1
                result = notification.get_string(
                    username=self.wp_user.user_login
                )

                if result:
                    human_list.append(result)

            if count >= limit:
                break

        return human_list
