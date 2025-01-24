"""
A set of models for user profiles
"""

from django.db import models


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
        "WPUser", on_delete=models.CASCADE, db_column="user_id"
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
    title = models.CharField(max_length=255)
    affiliation = models.CharField(max_length=255)
    twitter = models.CharField(max_length=255, blank=True)
    github = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    orcid = models.CharField(max_length=255, blank=True)
    mastodon = models.CharField(max_length=255, blank=True)
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
    title = models.TextField(blank=True, null=True)
    figshare_url = models.TextField(blank=True, null=True)
    commons_groups = models.TextField(blank=True, null=True)
    memberships = models.TextField(blank=True, null=True)
    recent_commons_activity = models.TextField(blank=True, null=True)

    commons_sites = models.TextField(blank=True, null=True)
    blog_posts = models.TextField(blank=True, null=True)
    cv = models.TextField(blank=True, null=True)

    facebook = models.TextField(blank=True, null=True)
    linkedin = models.TextField(blank=True, null=True)
    website = models.TextField(blank=True, null=True)

    """
    Upcoming Talks and Conferences
    Projects
    Education
    Publications
    About
    ORCID iD
    Twitter handle
    Site
    Institutional or Other Affiliation
    Title
    Figshare URL
    Academic Interests
    Commons Groups
    Recent Commons Activity
    Commons Sites
    Blog Posts
    Mastodon handle
    Name
    Memberships
    Facebook URL
    LinkedIn URL
    Website URL
    CORE Deposits
    CV
    Works Deposits
    Mastodon Feed
    """

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

    text = models.CharField(max_length=255)

    def __str__(self):
        """
        Return a human-readable representation of the AcademicInterest model
        instance as a string.

        Returns:
            str: The text of the academic interest.
        """
        return str(self.text)
