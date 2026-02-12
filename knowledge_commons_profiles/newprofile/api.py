"""
A class of API calls for user details
"""

import json
import logging
import re
from enum import Enum
from functools import cached_property
from operator import itemgetter
from pathlib import Path

import django
import phpserialize
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections
from django.db.models import Case
from django.db.models import CharField
from django.db.models import F
from django.db.models import Value
from django.db.models import When
from django.http import Http404

from knowledge_commons_profiles.__version__ import VERSION
from knowledge_commons_profiles.newprofile import mastodon
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import WpBlog
from knowledge_commons_profiles.newprofile.models import WpBpActivity
from knowledge_commons_profiles.newprofile.models import WpBpFollow
from knowledge_commons_profiles.newprofile.models import WpBpGroup
from knowledge_commons_profiles.newprofile.models import WpBpGroupMember
from knowledge_commons_profiles.newprofile.models import WpBpGroupsGroupmeta
from knowledge_commons_profiles.newprofile.models import WpBpNotification
from knowledge_commons_profiles.newprofile.models import WpBpUserBlogMeta
from knowledge_commons_profiles.newprofile.models import WpPostSubTable
from knowledge_commons_profiles.newprofile.models import WpUser
from knowledge_commons_profiles.newprofile.models import WpUserMeta
from knowledge_commons_profiles.newprofile.utils import get_profile_photo
from knowledge_commons_profiles.newprofile.works import HiddenWorks
from knowledge_commons_profiles.newprofile.works import WorksApiError
from knowledge_commons_profiles.newprofile.works import WorksDeposits

logger = logging.getLogger(__name__)

User = get_user_model()

MASTODON_MIN_SIGNS = 1
MASTODON_MAX_SIGNS = 2

DOMAIN_PATTERN = (
    r"^(((?!-))(xn--|_)?[a-z0-9-]{0,61}[a-z0-9]{1,1}\.)*(xn--)?"
    r"([a-z0-9][a-z0-9\-]{0,60}|[a-z0-9-]{1,30}\.[a-z]{2,})$"
)
DOMAIN_REGEX = re.compile(DOMAIN_PATTERN, re.IGNORECASE)


class ErrorModel(Enum):
    RAISE = 1
    RETURN = 2


class API:
    """
    A class containing API calls for user details
    """

    def __init__(
        self,
        request,
        user: str | Profile,
        use_wordpress=True,
        create=False,
        works_citation_style="MHRA",
    ):
        """
        Initialise the API class with a request and user object.
        """
        self.request = request
        self.user = user
        self.create = create

        self.use_wordpress = use_wordpress
        self._works_citation_style = works_citation_style

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
        self._wp_user_triggered = False

        if isinstance(user, Profile):
            self._profile = user
            self.user = user.username

    @property
    def works_citation_style(self):
        """
        Get the works citation style
        """
        return self._works_citation_style

    @works_citation_style.setter
    def works_citation_style(self, value):
        """
        Set the works citation style
        """
        self._works_citation_style = value

    def works_types(
        self,
        hidden_works: HiddenWorks = HiddenWorks.HIDE,
    ):
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
            self._works_types = (
                self._works_deposits.get_works_for_backend_edit(
                    hidden_works=hidden_works,
                    style=self._works_citation_style,
                )
            )

        return self._works_types

    @property
    def works_chart_json(self):
        """
        Get the works chart JSON
        """
        if self._works_deposits is None:
            self._works_deposits = WorksDeposits(
                self.user,
                "https://works.hcommons.org",
                user_profile=self.profile,
            )

        return self._works_deposits.get_vega_chart_json()

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
            self._works_html = (
                self._works_deposits.get_works_for_frontend_display(
                    style=self._works_citation_style
                )
            )

        return self._works_html

    @cached_property
    def works_deposits(self):
        """
        Get the works deposits
        """
        try:
            if self._works_deposits is None:
                self._works_deposits = WorksDeposits(
                    self.profile_info["username"],
                    "https://works.hcommons.org",
                )
        except WorksApiError:
            logger.exception(
                "An error was encountered. "
                "Assuming no works found for user: %s",
                self.user,
            )
            return None
        else:
            return self._works_deposits

    @cached_property
    def wp_user(self):
        """
        Get the WordPress user
        """
        if self._wp_user_triggered:
            return self._wp_user

        if self._wp_user is None:
            try:
                self._wp_user = WpUser.objects.get(user_login=self.user)
            except WpUser.DoesNotExist:
                self._wp_user_triggered = True
                self._wp_user = None

        self._wp_user_triggered = True
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
                (
                    self.mastodon_username,
                    self.mastodon_server,
                ) = self._get_mastodon_user_and_server(
                    mastodon_field=self._mastodon_profile
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
            logger.log(
                logging.INFO,
                "Unable to parse %s as a Mastodon profile",
                self.profile.mastodon,
            )
            return None, None

        # if the number of @ signs is not 2, we have a problem
        at_count = mastodon_field.count("@")
        if at_count < MASTODON_MIN_SIGNS or at_count > MASTODON_MAX_SIGNS:
            logger.log(
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
                logger.log(
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
                msg = f"Fetching info for {self.user}"
                logger.info(msg)
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
            "bluesky": self.profile.bluesky,
            "mastodon": self.profile.mastodon,
            "mastodon_username": m_user,
            "mastodon_server": m_server,
            "profile_image": get_profile_photo(self.profile),
            "works_username": self.profile.works_username,
            "publications": self.profile.publications,
            "projects": self.profile.projects,
            "memberships": self.profile.memberships,
            "institutional_or_other_affiliation": (
                self.profile.institutional_or_other_affiliation
            ),
            "profile": self.profile,
            "is_member_of": (
                json.loads(self.profile.is_member_of)
                if self.profile.is_member_of is not None
                else {}
            ),
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

        if not self.wp_user:
            return []

        cache_key = f"blog_post_list-{self.user}"
        cached_response = cache.get(cache_key, version=VERSION)

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
                version=VERSION,
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
            version=VERSION,
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

    def get_group_avatar_url(self, group_id: int) -> str:
        """
        Replicates BP's groups_avatar_upload_dir() logic and
        returns the full URL to the first “-bpfull” avatar image,
        or an empty string if none is found.
        """
        # 1) Your WP uploads root on disk, e.g.
        # '/var/www/html/wp-content/uploads'
        uploads_root = settings.WP_MEDIA_ROOT
        # 2) The corresponding URL prefix,
        # e.g. 'https://hcommons.org/app/uploads'
        uploads_url = settings.WP_MEDIA_URL

        # 3) Build the group-avatar directory path
        avatar_dir = Path(uploads_root) / Path("group-avatars") / str(group_id)

        # 4) Look for any “full” avatar file (e.g. 196c1430...-bpfull.png)
        matches = avatar_dir.glob("*-bpfull.*")

        for file in matches:
            return f"{uploads_url}/group-avatars/{group_id}/{file.name}"

        return ""

    def get_group(self, group_id, slug="", status_choices=None):
        """
        Get a group with a list of allowed status choices

        """
        # default to [("public","Public")]
        if status_choices is None:
            status_choices = WpBpGroup.STATUS_CHOICES[:1]

        # status_choices is either "public" or all the others
        status_keys = [key for key, label in status_choices]

        if len(status_keys) > 1:
            logger.info(
                "Privileged API call from %s", self.request.META["REMOTE_ADDR"]
            )

        # Try to fetch the group (or bail out with exception)
        if slug:
            grp = WpBpGroup.objects.get(slug=slug, status__in=status_keys)
        else:
            grp = WpBpGroup.objects.get(id=group_id, status__in=status_keys)

        # TODO: build the canonical URL
        url = f"/groups/{grp.slug}/"

        # Grab any avatar meta (your meta_key may be different)
        avatar_path = self.get_group_avatar_url(group_id=group_id)
        avatar = avatar_path if avatar_path else ""

        # Grab the groupblog ID → turn it into a blog URL
        blog_id = (
            WpBpGroupsGroupmeta.objects.filter(group=grp, meta_key="blog_id")
            .values_list("meta_value", flat=True)
            .first()
        )
        if blog_id:
            try:
                blog = WpBlog.objects.get(blog_id=blog_id)
                group_blog = f"https://{blog.domain}{blog.path}"
            except WpBlog.DoesNotExist:
                group_blog = ""
        else:
            group_blog = ""

        # Static arrays for upload/ moderate permissions
        upload_roles = ["member", "moderator", "administrator"]
        moderate_roles = ["moderator", "administrator"]

        return {
            "id": grp.id,
            "name": grp.name,
            "slug": grp.slug,
            "url": url,
            "visibility": grp.status,
            "description": grp.description or "",
            "avatar": avatar,
            "groupblog": group_blog,
            "upload_roles": upload_roles,
            "moderate_roles": moderate_roles,
        }

    def get_groups(
        self, status_choices=None, on_error: ErrorModel = ErrorModel.RAISE
    ):
        """
        Return a list of groups that the user is a member of
        :return:
        """
        if not self.wp_user:
            return []

        # default to [("public","Public")]
        if status_choices is None:
            status_choices = WpBpGroup.STATUS_CHOICES[:1]

        # status_choices is either "public" or all the others
        status_keys = [key for key, label in status_choices]

        if len(status_keys) > 1:
            logger.info(
                "Privileged API call from %s", self.request.META["REMOTE_ADDR"]
            )

        try:
            group_members = (
                WpBpGroupMember.objects.filter(
                    user_id=self.wp_user.id,
                    is_confirmed=True,
                    group__status__in=status_keys,
                )
                .select_related("group")
                .annotate(
                    gid=F("group__id"),
                    slug=F("group__slug"),
                    group_name=F("group__name"),
                    role=Case(
                        When(is_admin=True, then=Value("administrator")),
                        When(is_mod=True, then=Value("moderator")),
                        default=Value("member"),
                        output_field=CharField(),
                    ),
                )
                .order_by("group_name")
            )

            return [
                {
                    "id": gm.gid,  # group id
                    "group_name": gm.group_name,  # group name
                    "role": gm.role,  # computed role
                    "slug": gm.slug,  # slug
                    "status": gm.group.status,
                    "avatar": gm.group.get_avatar(),
                    "inviter_id": gm.inviter_id,
                }
                for gm in group_members
            ]

        except django.db.utils.OperationalError as oe:
            logger.warning(
                "Unable to connect to MySQL, fast-failing group data."
            )

            if on_error == ErrorModel.RAISE:
                raise

            return [], oe

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
        from knowledge_commons_profiles.newprofile.utils import (
            get_profile_photo as gpp,
        )

        return gpp(self.profile)

    def get_memberships(self):
        """
        Return a list of groups that the user is a member of
        :return:
        """
        cache_key = f"user_memberships-{self.user}"
        cached_response = cache.get(cache_key, version=VERSION)

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
                version=VERSION,
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
            logger.warning(
                "Unable to connect to MySQL, fast-failing profile data."
            )
            return False, None

    def get_user_blogs(self):
        """
        Return a list of user blogs
        :return:
        """
        if not self.wp_user:
            return []

        cache_key = f"user_blog_post_list-{self.user}"
        cached_response = cache.get(cache_key, version=VERSION)

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
            version=VERSION,
        )

        return sorted(results, key=itemgetter(0))

    def get_activity(self):
        """
        Return a list of user activities
        """
        if not self.wp_user:
            return None

        cache_key = f"user_activities_list-{self.user}"
        cached_response = cache.get(cache_key, version=VERSION)

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
            version=VERSION,
        )

        return distinct_objects[:5]

    def get_short_notifications(self):
        """
        Return an HTML-formatted list of user notifications
        """
        if not self.use_wordpress or not self.wp_user:
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
