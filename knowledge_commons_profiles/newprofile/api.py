"""
A class of API calls for user details
"""

import hashlib
import logging
import re
from functools import cached_property
from operator import itemgetter
from urllib.parse import urlencode

import django
import phpserialize
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections
from django.http import Http404

from knowledge_commons_profiles import newprofile
from knowledge_commons_profiles.newprofile import mastodon
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpBlog
from knowledge_commons_profiles.newprofile.models import WpBpActivity
from knowledge_commons_profiles.newprofile.models import WpBpFollow
from knowledge_commons_profiles.newprofile.models import WpBpGroupMember
from knowledge_commons_profiles.newprofile.models import WpBpNotification
from knowledge_commons_profiles.newprofile.models import WpBpUserBlogMeta
from knowledge_commons_profiles.newprofile.models import WpPostSubTable
from knowledge_commons_profiles.newprofile.models import WpUser
from knowledge_commons_profiles.newprofile.models import WpUserMeta
from knowledge_commons_profiles.newprofile.works import WorksDeposits

User = get_user_model()

MASTODON_MIN_SIGNS = 1
MASTODON_MAX_SIGNS = 2

DOMAIN_PATTERN = (
    r"^(((?!-))(xn--|_)?[a-z0-9-]{0,61}[a-z0-9]{1,1}\.)*(xn--)?"
    r"([a-z0-9][a-z0-9\-]{0,60}|[a-z0-9-]{1,30}\.[a-z]{2,})$"
)
DOMAIN_REGEX = re.compile(DOMAIN_PATTERN, re.IGNORECASE)


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
        self.create = create

        self.use_wordpress = use_wordpress

        # these fields are all loaded on first access via the cached_property
        # decorators below. This means you can init an API without triggering
        # any expensive calls
        self._profile = None
        self._wp_user = None
        self._profile_info = None
        self._mastodon_profile = None
        self.mastodon_username = None
        self.mastodon_server = None
        self._mastodon_posts = None
        self._works_deposits = None
        self._works_html = None
        self._works_types = None

    def works_types(self, sort=False):
        """
        Get the works types headings
        """
        if self._works_deposits is None:
            self._works_deposits = WorksDeposits(
                self.user,
                "https://works.hcommons.org",
                user_profile=self.profile,
            )

        if self._works_types is None:
            self._works_types = self._works_deposits.get_headings(sort=sort)

        return self._works_types

    @cached_property
    def works_html(self):
        """
        Get the works HTML
        """
        if self._works_deposits is None:
            try:
                self._works_deposits = WorksDeposits(
                    self.user,
                    "https://works.hcommons.org",
                    user_profile=self.profile,
                )
            except django.http.response.Http404:
                self._works_deposits = WorksDeposits(
                    None,
                    "https://works.hcommons.org",
                )

        if self._works_html is None:
            self._works_html = self._works_deposits.display_filter()

        return self._works_html

    @cached_property
    async def works_deposits(self):
        """
        Get the works deposits
        """
        if self._works_deposits is None:
            self._works_deposits = WorksDeposits(
                self.profile_info["username"],
                "https://works.hcommons.org",
            )
        return self._works_deposits

    @cached_property
    def wp_user(self):
        """
        Get the WordPress user
        """
        if self._wp_user is None:
            self._wp_user = WpUser.objects.get(user_login=self.user)
        return self._wp_user

    @cached_property
    def mastodon_posts(self):
        """
        Get the mastodon posts
        """
        # this triggers the population of all Mastodon fields
        _ = self.mastodon_profile
        return self._mastodon_posts

    @cached_property
    def mastodon_profile(self):
        """
        Get the mastodon profile
        """
        if self._mastodon_profile is None:
            self._mastodon_profile = self.profile_info["mastodon"]

            if self._mastodon_profile:
                self.mastodon_username, self.mastodon_server = (
                    self._get_mastodon_user_and_server(
                        mastodon_field=self._mastodon_profile
                    )
                )
                self._mastodon_posts = mastodon.MastodonFeed(
                    self.mastodon_username,
                    self.mastodon_server,
                )
        return self._mastodon_profile

    @property
    def mastodon_user_and_server(self):
        """
        Get the mastodon profile
        """
        return self._get_mastodon_user_and_server()

    def _get_mastodon_user_and_server(self, mastodon_field=None):
        """
        Get the mastodon profile
        """
        if self.mastodon_username and self.mastodon_server:
            return self.mastodon_username, self.mastodon_server

        mastodon_field = (
            mastodon_field if mastodon_field else self.profile.mastodon
        )

        if mastodon_field == "":
            return None, None

        # test if it's a string
        if not isinstance(mastodon_field, str):
            logging.log(
                logging.INFO,
                "Unable to parse %s as a Mastodon profile",
                self.profile.mastodon,
            )
            return None, None

        # if the number of @ signs is not 2, we have a problem
        at_count = mastodon_field.count("@")
        if at_count < MASTODON_MIN_SIGNS or at_count > MASTODON_MAX_SIGNS:
            logging.log(
                logging.INFO,
                "%s is not a valid Mastodon profile",
                self.profile.mastodon,
            )
            return None, None

        if mastodon_field:
            # select whether to slice off the first character ("@")
            if at_count == MASTODON_MAX_SIGNS:
                # 2 @ signs
                split_mastodon = mastodon_field[1:].split("@")
            else:
                # 1 @ sign
                split_mastodon = mastodon_field.split("@")

            split_one = split_mastodon[0]
            split_two = split_mastodon[1]

            self.mastodon_username, self.mastodon_server = (
                (split_one if split_one != "" else None),
                (split_two if split_two != "" else None),
            )

            # now verify that the server is a domain name
            is_domain = bool(
                DOMAIN_REGEX.match(
                    self.mastodon_server if self.mastodon_server else ""
                )
            )

            if not is_domain:
                logging.log(
                    logging.INFO,
                    "%s is not a valid domain in Mastodon parsing",
                    self.mastodon_server,
                )

            self.mastodon_username, self.mastodon_server = (
                (self.mastodon_username if is_domain else None),
                (self.mastodon_server if is_domain else None),
            )

        return self.mastodon_username, self.mastodon_server

    @cached_property
    def profile_info(self):
        """
        Get the profile info
        """
        if self._profile_info is None:
            self.get_profile_info()
        return self._profile_info

    @cached_property
    def profile(self):
        """
        Get the profile
        """
        if self._profile is None:
            try:
                self._profile = Profile.objects.prefetch_related(
                    "academic_interests",
                    "coverimage_set",
                ).get(username=self.user)
            except Profile.DoesNotExist:
                if self.create:
                    self._profile = Profile.objects.create(username=self.user)
                else:
                    # if the user exists but the Profile doesn't, then create
                    # it
                    try:
                        user_object = User.objects.get(username=self.user)
                        self._profile = Profile.objects.create(
                            username=self.user,
                            email=user_object.email,
                        )
                    except User.DoesNotExist as exc:
                        # raise 404
                        # use an assignment to avoid EM101
                        error_message = f"Profile not found: {self.user}"
                        raise Http404(error_message) from exc
        return self._profile

    def get_profile_info(self):
        """
        Returns a dictionary containing profile information about the user.

        Returns:
            A dictionary containing profile information.
        """

        m_user, m_server = self.mastodon_user_and_server

        # A dictionary containing profile information
        self._profile_info = {
            "name": self.profile.name,
            "username": self.profile.username,
            "title": self.profile.title,
            "affiliation": self.profile.affiliation,
            "twitter": self.profile.twitter,
            "github": self.profile.github,
            "email": self.profile.email,
            "orcid": self.profile.orcid,
            "mastodon": self.profile.mastodon,
            "mastodon_username": m_user,
            "mastodon_server": m_server,
            "profile_image": self.profile.profile_image,
            "works_username": self.profile.works_username,
            "publications": self.profile.publications,
            "projects": self.profile.projects,
            "memberships": self.profile.memberships,
            "institutional_or_other_affiliation": (
                self.profile.institutional_or_other_affiliation
            ),
            "profile": self.profile,
        }

        return self._profile_info

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
        Get blog posts from the WordPress database
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

        # check that these are all integers to avoid SQL injection possibility
        valid_blog_ids = [bid for bid in blog_ids if str(bid).isdigit()]

        counter = 0

        if len(valid_blog_ids) == 0:
            cache.set(
                cache_key,
                [],
                timeout=600,
                version=newprofile.__version__,
            )
            return []

        for num in valid_blog_ids:
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
                    WHERE p.post_author = %s
                    AND p.post_status='publish' AND p.post_type='post'
                """  # noqa: S608
                select_statements.append(select_stmt)

                counter += 1

        param_list = [self.wp_user.id] * counter

        # Combine all SELECT statements with UNION ALL
        final_query = "\nUNION ALL\n".join(select_statements)

        # (SQL injection should not be possible here)
        final_query = f"""
                    WITH unified_posts AS (
                        {final_query}
                    )
                    SELECT *
                    FROM unified_posts
                    ORDER BY post_date DESC
                    LIMIT 25
                """  # noqa: S608

        results = []

        results.extend(
            list(WpPostSubTable.objects.raw(final_query, param_list))
        )

        cache.set(
            cache_key,
            results,
            timeout=600,
            version=newprofile.__version__,
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
        return (
            WpBpGroupMember.objects.filter(
                user_id=self.wp_user.id,
                is_confirmed=True,
                group__status="public",
            )
            .prefetch_related("group")
            .order_by("group__name")
        )

    def get_cover_image(self):
        """
        Return the path to the user's cover image
        :return: a cover image
        """

        # TODO: this needs to fall-back to WordPress if we don't have a local
        #  image
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
        email = (
            self.profile.email
            if self.profile.email != "martin@martineve.com"
            else "martin@eve.gd"
        )
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
            meta_key="shib_ismemberof",
            user=self.wp_user,
        ).first()

        try:
            # this is double serialized
            decoded_list = phpserialize.unserialize(
                phpserialize.unserialize(meta_object.meta_value.encode()),
            )

            memberships = []

            # we're looking for things like this:
            # CO:COU:HASTAC:members:active
            for item in decoded_list:
                item_decoded = decoded_list[item].decode("utf-8")

                if item_decoded.startswith(
                    "CO:COU:"
                ) and item_decoded.endswith(
                    ":members:active",
                ):
                    society = item_decoded.split(":")[2]

                    if society != "HC":
                        memberships.append(society)

            cache.set(
                cache_key,
                memberships,
                timeout=600,
                version=newprofile.__version__,
            )

            return sorted(memberships)

        except Exception:  # noqa: BLE001
            return []

    def follower_count(self):
        """
        Return the number of followers
        :return: an integer
        """
        try:
            return (
                True,
                WpBpFollow.objects.filter(follower=self.wp_user).count(),
            )
        except django.db.utils.OperationalError:
            logging.warning(
                "Unable to connect to MySQL, fast-failing profile data."
            )
            return False, None

    def get_user_blogs(self):
        """
        Return a list of user blogs
        :return:
        """
        cache_key = f"user_blog_post_list-{self.user}"
        cached_response = cache.get(cache_key, version=newprofile.__version__)

        if cached_response is not None:
            return cached_response

        initial_sql = """
            SELECT DISTINCT
            b.blog_id,
            b.domain,
            u.user_email,
            b.public as is_public
            FROM wp_blogs b
            JOIN wp_usermeta um ON um.meta_key =
            CONCAT('wp_', b.blog_id, '_capabilities')
            JOIN wp_users u ON u.ID = um.user_id
            JOIN wp_blogmeta bm ON bm.blog_id = b.blog_id
            WHERE um.user_id = %s
            AND b.public = 1
            AND b.site_id = 2 # restrict to HC
            AND um.meta_value LIKE '%%administrator%%'
            GROUP BY b.domain
        """

        with connections["wordpress_dev"].cursor() as cursor:
            cursor.execute(initial_sql, [str(self.wp_user.id)])
            rows = cursor.fetchall()

        results = []

        for row in rows:
            blog_meta = WpBpUserBlogMeta.objects.select_related("blog").get(
                blog_id=row[0],
                meta_key="name",
            )

            results.append((blog_meta.meta_value, blog_meta.blog.domain))

        cache.set(
            cache_key,
            results,
            timeout=600,
            version=newprofile.__version__,
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
            user_id=self.wp_user.id,
            is_new=True,
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
                    username=self.wp_user.user_login,
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
                    username=self.wp_user.user_login,
                )

                if result:
                    human_list.append(result)

            if count >= limit:
                break

        return human_list
