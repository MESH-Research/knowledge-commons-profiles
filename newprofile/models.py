"""
A set of models for user profiles
"""

from django.db import models


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
        return self.name


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
        return self.text
