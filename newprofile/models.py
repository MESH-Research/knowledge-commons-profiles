"""
A set of models for user profiles
"""

# pylint: disable=too-few-public-methods,no-member

from django.db import models


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
        "WpUser", on_delete=models.CASCADE, db_column="post_author"
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
        max_length=128, default="", db_column="user-voice_username"
    )
    user_voice_slug = models.CharField(
        max_length=128, default="general", db_column="user-voice_slug"
    )
    user_voice_active = models.BooleanField(
        default=False, db_column="user-voice_active"
    )
    user_voice_alignment = models.CharField(
        max_length=5,
        choices=UserVoiceAlignment.choices,
        default=UserVoiceAlignment.RIGHT,
        db_column="user-voice_alignment",
    )
    user_voice_color = models.CharField(
        max_length=6, default="00BCBA", db_column="user-voice_color"
    )

    class Meta:
        """
        Metadata for the WpPost model
        """

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
        "WpUser", on_delete=models.CASCADE, db_column="post_author"
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
        max_length=128, default="", db_column="user-voice_username"
    )
    user_voice_slug = models.CharField(
        max_length=128, default="general", db_column="user-voice_slug"
    )
    user_voice_active = models.BooleanField(
        default=False, db_column="user-voice_active"
    )
    user_voice_alignment = models.CharField(
        max_length=5,
        choices=UserVoiceAlignment.choices,
        default=UserVoiceAlignment.RIGHT,
        db_column="user-voice_alignment",
    )
    user_voice_color = models.CharField(
        max_length=6, default="00BCBA", db_column="user-voice_color"
    )

    class Meta:
        """
        Metadata for the WpPost model
        """

        db_table = "wp_posts"
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
        "WpUser", on_delete=models.CASCADE, db_column="user_id"
    )
    value = models.TextField()
    last_updated = models.DateTimeField()

    class Meta:
        """
        Metadata for the WpProfileData model
        """

        db_table = "wp_bp_xprofile_data"

    def __str__(self):
        """
        Return a human-readable representation of the WpProfileData model
        :return:
        """
        return f"Profile data {self.field} for user {self.user.user_login}"


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
        default="0000-00-00 00:00:00", db_index=True
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
        indexes = [
            models.Index(fields=["user_login"], name="user_login_key"),
        ]

    def __str__(self):
        """
        Return a human-readable representation of the Wp_User model instance
        :return:
        """
        return str(self.user_login)


class Profile(models.Model):
    """
    A model for a user profile
    """

    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, db_index=True)
    central_user_id = models.IntegerField(db_index=True, null=True)
    title = models.CharField(max_length=255, null=True)
    affiliation = models.CharField(max_length=255)
    twitter = models.CharField(max_length=255, blank=True)
    github = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    orcid = models.CharField(max_length=255, blank=True)
    mastodon = models.CharField(max_length=255, blank=True)
    bluesky = models.CharField(max_length=255, blank=True)
    profile_image = models.URLField(blank=True)
    works_username = models.CharField(max_length=255, blank=True)
    academic_interests = models.ManyToManyField(
        "AcademicInterest", related_name="profiles"
    )
    about_user = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)

    upcoming_talks = models.TextField(blank=True, null=True)
    projects = models.TextField(blank=True, null=True)
    publications = models.TextField(blank=True, null=True)
    site = models.TextField(blank=True, null=True)
    institutional_or_other_affiliation = models.TextField(
        blank=True, null=True
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
    show_mastodon_feed = models.BooleanField(default=True)

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
