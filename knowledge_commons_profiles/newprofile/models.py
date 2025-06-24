"""
A set of models for user profiles
"""

import contextlib
import logging
import re
from typing import TYPE_CHECKING

import requests
from django.conf import settings

# pylint: disable=too-few-public-methods,no-member, too-many-ancestors
from django.db import models
from django_bleach.models import BleachField
from requests import Response

if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)

HTTP_200_OK = 200

CITATION_STYLE_CHOICES = [(key, key) for key in settings.CITATION_STYLES]


# ruff: noqa: PLC0415
class ProfileBleachField(BleachField):
    """An override of BleachField to avoid casting SafeString from db
    Bleachfield automatically casts the default return type (string) into
    a SafeString, which is okay when using the value for HTML rendering but
    not when using the value elsewhere (XML encoding)
    https://github.com/marksweb/django-bleach/blob/504b3784c525886ba1974eb9ecbff89314688491/django_bleach/models.py#L76
    """

    def from_db_value(self, value, expression, connection):
        """
        Create from DB
        """
        return value

    def pre_save(self, model_instance, *args, **kwargs):
        """
        Filter the model
        """
        return super().pre_save(model_instance, *args, **kwargs)


class WpPostSubTable(models.Model):
    """
    A model for a WordPress post
    """

    class UserVoiceAlignment(models.TextChoices):
        """
        An enum for user voice alignment
        """

        LEFT = "left", "Left"
        RIGHT = "right", "Right"

    id = models.BigAutoField(primary_key=True, db_column="ID")
    post_author = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="post_author",
    )
    blogname = models.CharField(max_length=255, default="")
    blogdomain = models.CharField(max_length=255, default="")
    blogpath = models.CharField(max_length=255, default="")
    post_date = models.DateTimeField(default="0000-00-00 00:00:00")
    post_date_gmt = models.DateTimeField(default="0000-00-00 00:00:00")
    post_content = models.TextField()
    post_title = models.TextField()
    post_excerpt = models.TextField()
    post_status = models.CharField(max_length=20, default="publish")
    comment_status = models.CharField(max_length=20, default="open")
    ping_status = models.CharField(max_length=20, default="open")
    post_password = models.CharField(max_length=255, default="")
    post_name = models.CharField(max_length=200, default="", db_index=True)
    to_ping = models.TextField()
    pinged = models.TextField()
    post_modified = models.DateTimeField(default="0000-00-00 00:00:00")
    post_modified_gmt = models.DateTimeField(default="0000-00-00 00:00:00")
    post_content_filtered = models.TextField()
    post_parent = models.BigIntegerField(default=0, db_index=True)
    guid = models.CharField(max_length=255, default="")
    menu_order = models.IntegerField(default=0)
    post_type = models.CharField(max_length=20, default="post")
    post_mime_type = models.CharField(max_length=100, default="")
    comment_count = models.BigIntegerField(default=0)
    user_voice_username = models.CharField(
        max_length=128,
        default="",
        db_column="user-voice_username",
    )
    user_voice_slug = models.CharField(
        max_length=128,
        default="general",
        db_column="user-voice_slug",
    )
    user_voice_active = models.BooleanField(
        default=False,
        db_column="user-voice_active",
    )
    user_voice_alignment = models.CharField(
        max_length=5,
        choices=UserVoiceAlignment.choices,
        default=UserVoiceAlignment.RIGHT,
        db_column="user-voice_alignment",
    )
    user_voice_color = models.CharField(
        max_length=6,
        default="00BCBA",
        db_column="user-voice_color",
    )

    class Meta:
        """
        Metadata for the WpPost model
        """

        app_label = "newprofile"
        managed = False
        db_table = "wp_posts"

    def __str__(self):
        """
        Return a human-readable representation of the WpPost model
        :return:
        """
        return str(self.post_title)


class WpPost(models.Model):
    """
    A model for a WordPress post
    """

    class UserVoiceAlignment(models.TextChoices):
        """
        An enum for user voice alignment
        """

        LEFT = "left", "Left"
        RIGHT = "right", "Right"

    id = models.BigAutoField(primary_key=True, db_column="ID")
    post_author = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="post_author",
    )
    post_date = models.DateTimeField(default="0000-00-00 00:00:00")
    post_date_gmt = models.DateTimeField(default="0000-00-00 00:00:00")
    post_content = models.TextField()
    post_title = models.TextField()
    post_excerpt = models.TextField()
    post_status = models.CharField(max_length=20, default="publish")
    comment_status = models.CharField(max_length=20, default="open")
    ping_status = models.CharField(max_length=20, default="open")
    post_password = models.CharField(max_length=255, default="")
    post_name = models.CharField(max_length=200, default="", db_index=True)
    to_ping = models.TextField()
    pinged = models.TextField()
    post_modified = models.DateTimeField(default="0000-00-00 00:00:00")
    post_modified_gmt = models.DateTimeField(default="0000-00-00 00:00:00")
    post_content_filtered = models.TextField()
    post_parent = models.BigIntegerField(default=0, db_index=True)
    guid = models.CharField(max_length=255, default="")
    menu_order = models.IntegerField(default=0)
    post_type = models.CharField(max_length=20, default="post")
    post_mime_type = models.CharField(max_length=100, default="")
    comment_count = models.BigIntegerField(default=0)
    user_voice_username = models.CharField(
        max_length=128,
        default="",
        db_column="user-voice_username",
    )
    user_voice_slug = models.CharField(
        max_length=128,
        default="general",
        db_column="user-voice_slug",
    )
    user_voice_active = models.BooleanField(
        default=False,
        db_column="user-voice_active",
    )
    user_voice_alignment = models.CharField(
        max_length=5,
        choices=UserVoiceAlignment.choices,
        default=UserVoiceAlignment.RIGHT,
        db_column="user-voice_alignment",
    )
    user_voice_color = models.CharField(
        max_length=6,
        default="00BCBA",
        db_column="user-voice_color",
    )

    class Meta:
        """
        Metadata for the WpPost model
        """

        app_label = "newprofile"
        db_table = "wp_posts"
        managed = False
        indexes = [
            models.Index(
                fields=["post_type", "post_status", "post_date", "id"],
                name="type_status_date",
            ),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpPost model
        :return:
        """
        return str(self.post_title)


class WpBlog(models.Model):
    """
    A model for a WordPress blog
    """

    blog_id = models.BigAutoField(primary_key=True)
    site_id = models.BigIntegerField(default=0)
    domain = models.CharField(max_length=200, default="")
    path = models.CharField(max_length=100, default="")
    registered = models.DateTimeField(default="0000-00-00 00:00:00")
    last_updated = models.DateTimeField(default="0000-00-00 00:00:00")
    public = models.SmallIntegerField(default=1)
    archived = models.SmallIntegerField(default=0)
    mature = models.SmallIntegerField(default=0)
    spam = models.SmallIntegerField(default=0)
    deleted = models.SmallIntegerField(default=0)
    lang_id = models.IntegerField(default=0, db_index=True)

    class Meta:
        """
        Metadata for the WpBlog model
        """

        db_table = "wp_blogs"
        managed = False
        indexes = [
            models.Index(fields=["domain", "path"], name="domain"),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBlog model

        """
        return str(self.domain)


class WpProfileData(models.Model):
    """
    A model for WordPress user profile data
    """

    id = models.BigAutoField(primary_key=True)
    field = models.ForeignKey(
        "WpProfileFields",
        on_delete=models.CASCADE,
        db_column="field_id",
    )
    user = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="user_id",
    )
    value = models.TextField()
    last_updated = models.DateTimeField()

    class Meta:
        """
        Metadata for the WpProfileData model
        """

        managed = False
        db_table = "wp_bp_xprofile_data"

    def __str__(self):
        """
        Return a human-readable representation of the WpProfileData model
        :return:
        """
        try:

            return (
                f"Profile data {self.field} for user "
                f"{self.user.user_login}: {self.value}"
            )
        except WpProfileFields.DoesNotExist:
            return self.value


class WpProfileFields(models.Model):
    """
    A model for WordPress user profile fields
    """

    id = models.BigAutoField(primary_key=True)
    group_id = models.BigIntegerField(db_index=True)
    parent_id = models.BigIntegerField(db_index=True)
    type = models.CharField(max_length=150)
    name = models.CharField(max_length=150)
    description = models.TextField()
    is_required = models.BooleanField(default=False, db_index=True)
    is_default_option = models.BooleanField(default=False)
    field_order = models.BigIntegerField(default=0, db_index=True)
    option_order = models.BigIntegerField(default=0)
    order_by = models.CharField(max_length=15, default="")
    can_delete = models.BooleanField(default=True, db_index=True)

    class Meta:
        """
        Metadata for the WpProfileFields model
        """

        managed = False
        db_table = "wp_bp_xprofile_fields"

    def __str__(self):
        """
        Return a human-readable representation of the WpProfileFields model
        instance as a string.

        Returns:
            str: The name of the profile field.
        """
        return str(self.name)


class WpUser(models.Model):
    """
    A model for a WordPress user
    """

    id = models.BigAutoField(primary_key=True, db_column="ID")
    user_login = models.CharField(max_length=60, unique=True, default="")
    user_pass = models.CharField(max_length=255, default="")
    user_nicename = models.CharField(max_length=50, default="", db_index=True)
    user_email = models.CharField(max_length=100, default="", db_index=True)
    user_url = models.CharField(max_length=100, default="")
    user_registered = models.DateTimeField(
        default="0000-00-00 00:00:00",
        db_index=True,
    )
    user_activation_key = models.CharField(max_length=255, default="")
    user_status = models.IntegerField(default=0)
    display_name = models.CharField(max_length=250, default="")
    spam = models.SmallIntegerField(default=0)
    deleted = models.SmallIntegerField(default=0)

    class Meta:
        """
        Metadata for the WpUser model
        """

        db_table = "wp_users"
        managed = False
        indexes = [
            models.Index(fields=["user_login"], name="user_login_key"),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the Wp_User model instance
        :return:
        """
        return str(self.user_login)

    @staticmethod
    def get_user_data(
        output_stream: "SupportsWrite[str] | None" = None, limit: int = -1
    ) -> "QuerySet[WpUser]":
        """
        Return an annotated list of all users
        """
        from knowledge_commons_profiles.newprofile.build_users_cache import (
            get_user_data,
        )

        return get_user_data(output_stream=output_stream, limit=limit)


class Profile(models.Model):
    """
    A model for a user profile
    """

    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, db_index=True)
    central_user_id = models.IntegerField(db_index=True, null=True)
    title = models.CharField(max_length=255, null=True)
    affiliation = models.CharField(max_length=255, null=True)
    twitter = models.CharField(max_length=255, blank=True)
    github = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    orcid = models.CharField(max_length=255, blank=True, db_index=True)
    mastodon = models.CharField(max_length=255, blank=True)
    bluesky = models.CharField(max_length=255, blank=True)
    profile_image = models.URLField(blank=True)
    works_username = models.CharField(max_length=255, blank=True)
    academic_interests = models.ManyToManyField(
        "AcademicInterest", related_name="profiles", blank=True
    )
    about_user = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)

    upcoming_talks = models.TextField(blank=True, null=True)
    projects = models.TextField(blank=True, null=True)
    publications = models.TextField(blank=True, null=True)
    site = models.TextField(blank=True, null=True)
    institutional_or_other_affiliation = models.TextField(
        blank=True,
        null=True,
    )
    figshare_url = models.TextField(blank=True, null=True)
    commons_groups = models.TextField(blank=True, null=True)
    memberships = models.TextField(blank=True, null=True)
    recent_commons_activity = models.TextField(blank=True, null=True)

    commons_sites = models.TextField(blank=True, null=True)
    blog_posts = models.TextField(blank=True, null=True)
    cv = models.TextField(blank=True, null=True)

    cv_file = models.FileField(
        upload_to="cvs/",
        blank=True,
        null=True,
        help_text="Upload your CV (PDF format recommended)",
    )

    facebook = models.TextField(blank=True, null=True)
    linkedin = models.TextField(blank=True, null=True)
    website = models.TextField(blank=True, null=True)

    # visibility settings
    show_academic_interests = models.BooleanField(default=True)
    show_projects = models.BooleanField(default=True)
    show_publications = models.BooleanField(default=True)
    show_talks = models.BooleanField(default=True)
    show_cv = models.BooleanField(default=True)
    show_bio = models.BooleanField(default=True)
    show_education = models.BooleanField(default=True)
    show_about_user = models.BooleanField(default=True)
    show_works = models.BooleanField(default=True)
    show_blog_posts = models.BooleanField(default=True)
    show_commons_groups = models.BooleanField(default=True)
    show_commons_sites = models.BooleanField(default=True)
    show_mastodon_feed = models.BooleanField(default=True)
    show_recent_activity = models.BooleanField(default=True)

    left_order = models.CharField(max_length=255, blank=True, null=True)
    right_order = models.CharField(max_length=255, blank=True, null=True)
    works_order = models.TextField(blank=True, null=True)
    works_show = models.TextField(blank=True, null=True)
    works_work_show = models.TextField(blank=True, null=True)
    reference_style = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default="MHRA",
        choices=CITATION_STYLE_CHOICES,
    )

    external_sync_ids = models.TextField(blank=True, null=True)
    is_member_of = models.TextField(blank=True, null=True)
    in_membership_groups = models.TextField(blank=True, null=True)

    def __str__(self):
        """
        Return a human-readable representation of the Profile model instance
        as a string.

        Returns:
            str: The name of the profile.
        """
        return str(self.name)


class AcademicInterest(models.Model):
    """
    A model for an academic interest
    """

    text = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        """
        Return a human-readable representation of the AcademicInterest model
        instance as a string.

        Returns:
            str: The text of the academic interest.
        """
        return str(self.text)


class WpBpGroupMember(models.Model):
    """
    A model for a WordPress group member
    """

    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        "WpBpGroup",
        on_delete=models.CASCADE,
        db_column="group_id",
    )
    user = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="group_memberships",
    )
    inviter_id = models.BigIntegerField(db_index=True)
    is_admin = models.BooleanField(default=False, db_index=True)
    is_mod = models.BooleanField(default=False, db_index=True)
    user_title = models.CharField(max_length=100)
    date_modified = models.DateTimeField()
    comments = models.TextField()
    is_confirmed = models.BooleanField(default=False, db_index=True)
    is_banned = models.BooleanField(default=False)
    invite_sent = models.BooleanField(default=False)

    class Meta:
        """
        Metadata for the WpBpGroupMember model
        """

        db_table = "wp_bp_groups_members"
        managed = False
        indexes = [
            models.Index(fields=["group_id"]),
            models.Index(fields=["is_admin"]),
            models.Index(fields=["is_mod"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["inviter_id"]),
            models.Index(fields=["is_confirmed"]),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpGroupMember model
        instance as a string.
        """
        return str(self.user) + " in " + str(self.group)


class WpBpGroupsGroupmeta(models.Model):
    """
    Mirrors the BuddyPress `wp_bp_groups_groupmeta` table.
    """

    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(
        "WpBpGroup",
        on_delete=models.DO_NOTHING,
        db_column="group_id",
        related_name="meta",
    )
    meta_key = models.CharField(max_length=255)
    meta_value = models.TextField()

    class Meta:
        db_table = "wp_bp_groups_groupmeta"
        managed = False

    def __str__(self):
        """
        String representation of the WpBpGroupsGroupmeta model
        """
        return str(self.group)


class WpBpGroup(models.Model):
    """
    A model for a WordPress group
    """

    # NOTE: the ordering here is important. Public must be first.
    # See get_groups in api.py to see why.
    # In fact, don't change this. It will break things.
    STATUS_CHOICES = (
        ("public", "Public"),
        ("private", "Private"),
        ("hidden", "Hidden"),
    )

    id = models.BigAutoField(primary_key=True)
    creator = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="creator_id",
    )
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="public",
        db_index=True,
    )
    enable_forum = models.BooleanField(default=True)
    date_created = models.DateTimeField()
    parent_id = models.BigIntegerField(default=0, db_index=True)

    class Meta:
        """
        Metadata for the WpBpGroup model
        """

        db_table = "wp_bp_groups"
        managed = False
        indexes = [
            models.Index(fields=["creator_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["parent_id"]),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpGroup model
        instance as a string.
        """
        return str(self.name)


class WpUserMeta(models.Model):
    """
    A model for a WordPress user meta
    """

    umeta_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="user_id",
    )
    meta_key = models.CharField(max_length=255, null=True, db_index=True)
    meta_value = models.TextField(null=True)

    class Meta:
        """
        Metadata for the WpUserMeta model
        """

        db_table = "wp_usermeta"
        managed = False
        indexes = [models.Index(fields=["meta_key"], name="meta_key_idx")]

    def __str__(self):
        """
        Return a human-readable representation of the WpUserMeta model
        instance as a string.
        """
        return str(self.meta_key)


class CoverImage(models.Model):
    """
    A model for a cover image
    """

    profile = models.ForeignKey(
        "Profile",
        on_delete=models.CASCADE,
        null=True,
        default="",
    )
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """
        Return a human-readable representation of the CoverImage model
        instance as a string.
        """
        return str(self.filename)


class ProfileImage(models.Model):
    """
    A model for a profile image
    """

    profile = models.ForeignKey(
        "Profile",
        on_delete=models.CASCADE,
        null=True,
        default="",
    )
    thumb = models.CharField(max_length=255)
    full = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """
        Return a human-readable representation of the ProfileImage model
        instance as a string.
        """
        return str(self.full)


class WpTermTaxonomy(models.Model):
    """
    A model for a WordPress term taxonomy
    """

    term_taxonomy_id = models.BigAutoField(primary_key=True)
    term_id = models.BigIntegerField()
    taxonomy = models.CharField(max_length=32)
    description = models.TextField()
    parent = models.BigIntegerField(default=0)
    count = models.BigIntegerField(default=0)

    class Meta:
        """
        Metadata for the WpTermTaxonomy model
        """

        db_table = "wp_term_taxonomy"
        unique_together = (("term_id", "taxonomy"),)
        managed = False
        indexes = [models.Index(fields=["taxonomy"])]

    def __str__(self):
        """
        Return a human-readable representation of the WpTermTaxonomy model
        """
        return str(self.description)


class WpTermRelationships(models.Model):
    """
    A model for a WordPress term relationship
    """

    object_id = models.BigIntegerField(primary_key=True)
    term_taxonomy = models.ForeignKey(
        WpTermTaxonomy,
        on_delete=models.CASCADE,
        db_column="term_taxonomy_id",
    )
    term_order = models.IntegerField(default=0)

    class Meta:
        """
        Metadata for the WpTermRelationships model
        """

        db_table = "wp_term_relationships"
        managed = False
        indexes = [models.Index(fields=["term_taxonomy"])]

    def __str__(self):
        """
        Return a human-readable representation of the WpTermRelationships model
        """
        return str(self.term_taxonomy)


class WpBpFollow(models.Model):
    """
    A model for a WordPress follow
    """

    id = models.BigAutoField(primary_key=True)
    leader = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="leader_id",
        related_name="following",
    )
    follower = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="follower_id",
        related_name="followers",
    )
    follow_type = models.CharField(max_length=75)
    date_recorded = models.DateTimeField()

    class Meta:
        """
        Metadata for the WpBpFollow model
        """

        managed = False
        db_table = "wp_bp_follow"
        indexes = [
            models.Index(fields=["leader", "follower"], name="followers"),
            models.Index(fields=["follow_type"]),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpFollow model
        """
        return str(self.follower) + " following " + str(self.leader)


class WpBpUserBlogMeta(models.Model):
    """
    A model for a WordPress blog meta
    """

    id = models.BigAutoField(primary_key=True)
    blog = models.ForeignKey(
        "WpBlog",
        on_delete=models.CASCADE,
        db_column="blog_id",
    )
    meta_key = models.CharField(max_length=255, null=True)
    meta_value = models.TextField(null=True)

    class Meta:
        """
        Metadata for the WpBpUserBlogMeta model
        """

        db_table = "wp_bp_user_blogs_blogmeta"
        managed = False
        indexes = [
            models.Index(fields=["blog_id"]),
            models.Index(fields=["meta_key"]),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpUserBlogMeta model
        """
        return str(self.meta_key) + " for " + str(self.blog)


class WpBpActivity(models.Model):
    """
    A model for a WordPress activity
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="user_id",
    )
    component = models.CharField(max_length=75)
    type = models.CharField(max_length=75)
    action = models.TextField()
    content = models.TextField()
    primary_link = models.TextField()
    item_id = models.BigIntegerField()
    secondary_item_id = models.BigIntegerField(null=True)
    date_recorded = models.DateTimeField()
    hide_sitewide = models.BooleanField(default=False)
    mptt_left = models.IntegerField(default=0)
    mptt_right = models.IntegerField(default=0)
    is_spam = models.BooleanField(default=False)

    class Meta:
        """
        Metadata for the WpBpActivity model
        """

        db_table = "wp_bp_activity"
        managed = False
        indexes = [
            models.Index(fields=["date_recorded"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["item_id"]),
            models.Index(fields=["secondary_item_id"]),
            models.Index(fields=["component"]),
            models.Index(fields=["type"]),
            models.Index(fields=["mptt_left"]),
            models.Index(fields=["mptt_right"]),
            models.Index(fields=["hide_sitewide"]),
            models.Index(fields=["is_spam"]),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpActivity model
        """
        return str(self.user) + " " + str(self.type)


class WpBpActivityMeta(models.Model):
    """
    A model for a WordPress activity meta
    """

    id = models.BigAutoField(primary_key=True)
    activity = models.ForeignKey(
        "WpBpActivity",
        on_delete=models.CASCADE,
        db_column="activity_id",
        related_name="meta",
    )
    meta_key = models.CharField(max_length=255, null=True)
    meta_value = models.TextField(null=True)

    class Meta:
        """
        Metadata for the WpBpActivityMeta model
        """

        db_table = "wp_bp_activity_meta"
        indexes = [models.Index(fields=["meta_key"])]
        managed = False

    def __str__(self):
        """
        Return a human-readable representation of the WpBpActivityMeta model
        """
        return str(self.activity)


class WpBpNotification(models.Model):
    """
    A model for a WordPress notification
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "WpUser",
        on_delete=models.CASCADE,
        db_column="user_id",
    )
    item_id = models.BigIntegerField()
    secondary_item_id = models.BigIntegerField(null=True)
    component_name = models.CharField(max_length=75)
    component_action = models.CharField(max_length=75)
    date_notified = models.DateTimeField()
    is_new = models.BooleanField(default=False)

    class Meta:
        """
        Metadata for the WpBpNotification model
        """

        db_table = "wp_bp_notifications"
        managed = False
        indexes = [
            models.Index(fields=["item_id"]),
            models.Index(fields=["secondary_item_id"]),
            models.Index(fields=["is_new"]),
            models.Index(fields=["component_name"]),
            models.Index(fields=["component_action"]),
            models.Index(fields=["user", "is_new"], name="useritem"),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the WpBpNotification model
        """
        # pylint: disable=import-outside-toplevel
        from knowledge_commons_profiles.newprofile import notifications

        return str(notifications.BuddyPressNotification(self))

    def get_string(self, username):
        """
        Get a string representation of the notification without aggregation
        """
        # pylint: disable=import-outside-toplevel
        from knowledge_commons_profiles.newprofile import notifications

        return notifications.BuddyPressNotification(self).get_string(
            username=username,
        )

    def get_short_string(self, username):
        """
        Get a short string representation of the notification for the dropdown
        """
        # pylint: disable=import-outside-toplevel
        from knowledge_commons_profiles.newprofile import notifications

        return notifications.BuddyPressNotification(self).get_string(
            short=True,
            username=username,
        )


class RORRecord(models.Model):
    """
    A record corresponding to an ROR record
    """

    ror_id: str = models.URLField(blank=True, null=True)
    institution_name: str = models.TextField(blank=True, null=True)
    grid_id: str = models.CharField(max_length=255, blank=True, null=True)
    country: str = models.CharField(max_length=255, blank=True, null=True)
    lat: float = models.FloatField(null=True)
    lon: float = models.FloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=["institution_name"]),
            models.Index(fields=["ror_id"]),
        ]

    def __str__(self) -> str:
        """
        A string representation of the ROR record
        :return:
        """
        return (
            self.institution_name
            + ", "
            + self.country
            + " ("
            + self.ror_id
            + ")"
        )


class RORLookup(models.Model):
    """
    A model for a ROR lookup
    """

    id: int = models.BigAutoField(primary_key=True)
    ror: RORRecord = models.ForeignKey(
        RORRecord, on_delete=models.CASCADE, null=True, blank=True
    )
    text: str = models.TextField()

    class Meta:
        """
        Metadata for the RORLookup model
        """

        indexes = [
            models.Index(fields=["text"], name="idx_rorlookup_text"),
        ]

    def __str__(self) -> str:
        """
        A string representation of the ROR lookup
        :return:
        """
        return str(self.ror)

    @staticmethod
    def replace_at_end(text: str, old_suffix: str, new_suffix: str):
        """
        Replaces 'old_suffix' with 'new_suffix' in 'text' only if 'old_suffix'
        is found at the end of the string.

        Args:
            text: The original string.
            old_suffix: The suffix to be replaced.
            new_suffix: The new suffix to replace with.

        Returns:
            The modified string, or the original string if the suffix is
            not found.
        """
        if text.endswith(old_suffix):
            return re.sub(re.escape(old_suffix) + r"$", new_suffix, text)
        return text

    @staticmethod
    def lookup(text: str) -> "RORLookup | None":
        # see if we have an existing match
        # if not, consult the ROR API to find one

        if text == "" or text is None:
            return None

        replaced_text = text.replace("U of", "University of")
        replaced_text = RORLookup.replace_at_end(
            replaced_text, " U", " University"
        )
        replaced_text = RORLookup.replace_at_end(
            replaced_text, " U.", " University"
        )
        replaced_text.replace("comm C", "Community College")
        replaced_text.replace("Comm C", "Community College")
        replaced_text.replace("comm C.", "Community College")
        replaced_text.replace("Comm C", "Community College")

        with contextlib.suppress(RORLookup.DoesNotExist):
            ror_lookup: RORLookup = RORLookup.objects.get(text=text)
            logger.info("Found existing ROR lookup: %s", ror_lookup)
            return ror_lookup

        # see if there's a precise ROR
        ror_lookup: RORLookup | None = RORLookup.check_for_precise_ror(text)

        if ror_lookup:
            return ror_lookup

        # See if the ROR API can return us a match
        # we use the ROR query API at
        # https://api.ror.org/v2/organizations?affiliation=

        url: str = (
            "https://api.ror.org/v2/organizations?affiliation=" + replaced_text
        )

        logger.info("ROR lookup: %s", url)
        response: Response = requests.get(url, timeout=settings.ROR_TIMEOUT)

        if response.status_code == HTTP_200_OK:
            response.raise_for_status()

            results: dict = response.json()

            if len(results["items"]) > 0:
                chosen: bool = results["items"][0]["chosen"]
                score: int = results["items"][0]["score"]

                if chosen or score > settings.ROR_THRESHOLD:
                    with contextlib.suppress(RORRecord.DoesNotExist):
                        ror = RORLookup.get_ror(results)

                        return RORLookup.objects.get_or_create(
                            ror=ror,
                            text=text,
                        )[0]

        logger.info("ROR lookup failed: %s", text)
        return None

    @staticmethod
    def get_ror(results) -> RORRecord:
        """
        Get the ROR record
        """
        ror_id: str = results["items"][0]["organization"]["id"]
        ror: RORRecord = RORRecord.objects.get(ror_id=ror_id)
        # Found ROR match
        logger.info("Found ROR match: %s", ror)
        return ror

    @staticmethod
    def check_for_precise_ror(text: str) -> "RORLookup | None":
        """
        Check if we have a precise ROR and create a lookup
        """
        with contextlib.suppress(RORRecord.DoesNotExist, IndexError):
            try:
                ror_lookup: RORLookup = RORLookup.objects.get_or_create(
                    ror=RORRecord.objects.get(institution_name=text),
                    text=text,
                )[0]
            except RORRecord.MultipleObjectsReturned:
                ror_lookup: RORLookup = RORLookup.objects.get_or_create(
                    ror=RORRecord.objects.filter(institution_name=text)[0],
                    text=text,
                )[0]

                logger.info("Found precise ROR: %s", ror_lookup)
                return ror_lookup

            logger.info("Found precise ROR: %s", ror_lookup)
            return ror_lookup

        return None

    @staticmethod
    def get_affiliation(
        wp_user_dict: dict[str, str | WpUser],
    ) -> RORRecord | str:
        """
        Get the affiliation for a user
        """
        # see if there's a RORLookup
        ror_lookup: RORLookup | None = None

        with contextlib.suppress(RORLookup.DoesNotExist):
            ror_lookup: RORLookup | None = RORLookup.objects.filter(
                text=wp_user_dict["institution"]
            ).first()

        if ror_lookup:
            return ror_lookup.ror

        return wp_user_dict["institution"]


class UserStats(models.Model):
    # Integer fields
    user_count = models.IntegerField()
    user_count_active = models.IntegerField()

    # Everything else as TextFields
    user_count_active_two = models.TextField()
    user_count_active_three = models.TextField()
    years = models.TextField()
    data = models.TextField()
    latlong = models.TextField()
    topinsts = models.TextField()
    topinstscount = models.TextField()
    emails = models.TextField()
    emailcount = models.TextField()

    def __str__(self):
        return (
            f"Stats(pk={self.pk}, users={self.user_count}, "
            f"active={self.user_count_active})"
        )
