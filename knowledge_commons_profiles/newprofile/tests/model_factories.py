"""Factory classes for knowledge commons profile models.

This module provides factory classes for creating test instances of models
in the knowledge_commons_profiles application.
"""

from typing import Any

import factory
from django.contrib.auth.models import User
from faker import Faker

from knowledge_commons_profiles.newprofile import models

fake = Faker()


class WpPostFactory(factory.Factory):
    """Factory for creating WpPost model instances.

    This factory generates test instances of the WpPost model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpPost


class WpBlogFactory(factory.Factory):
    """Factory for creating WpBlog model instances.

    This factory generates test instances of the WpBlog model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBlog


class WpProfileFieldsFactory(factory.Factory):
    """Factory for creating WpProfileFields model instances.

    This factory generates test instances of the WpProfileFields model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpProfileFields


class WpUserFactory(factory.Factory):
    """Factory for creating WpUser model instances.

    This factory generates test instances of the WpUser model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpUser


class WpBpGroupFactory(factory.Factory):
    """Factory for creating WpBpGroup model instances.

    This factory generates test instances of the WpBpGroup model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpGroup


class WpBpGroupMemberFactory(factory.Factory):
    """Factory for creating WpBpGroupMember model instances.

    This factory generates test instances of the WpBpGroupMember model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpGroupMember

    user: Any = factory.SubFactory(WpUserFactory)
    group: Any = factory.SubFactory(WpBpGroupFactory)


class WpProfileDataFactory(factory.Factory):
    """Factory for creating WpProfileData model instances.

    This factory generates test instances of the WpProfileData model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpProfileData

    field: Any = factory.SubFactory(WpProfileFieldsFactory)
    user: Any = factory.SubFactory(WpUserFactory)


class WpUserMetaFactory(factory.Factory):
    """Factory for creating WpUserMeta model instances.

    This factory generates test instances of the WpUserMeta model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpUserMeta


class WpTermTaxonomyFactory(factory.Factory):
    """Factory for creating WpTermTaxonomy model instances.

    This factory generates test instances of the WpTermTaxonomy model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpTermTaxonomy


class WpTermRelationshipsFactory(factory.Factory):
    """Factory for creating WpTermRelationships model instances.

    This factory generates test instances of the WpTermRelationships model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpTermRelationships

    term_taxonomy: Any = factory.SubFactory(WpTermTaxonomyFactory)


class WpBpFollowFactory(factory.Factory):
    """Factory for creating WpBpFollow model instances.

    This factory generates test instances of the WpBpFollow model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpFollow

    follower: Any = factory.SubFactory(WpUserFactory)
    leader: Any = factory.SubFactory(WpUserFactory)


class WpBpUserBlogMetaFactory(factory.Factory):
    """Factory for creating WpBpUserBlogMeta model instances.

    This factory generates test instances of the WpBpUserBlogMeta model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpUserBlogMeta

    blog: Any = factory.SubFactory(WpBlogFactory)


class WpBpActivityFactory(factory.Factory):
    """Factory for creating WpBpActivity model instances.

    This factory generates test instances of the WpBpActivity model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpActivity

    user: Any = factory.SubFactory(WpUserFactory)


class WpBpActivityMetaFactory(factory.Factory):
    """Factory for creating WpBpActivityMeta model instances.

    This factory generates test instances of the WpBpActivityMeta model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpActivityMeta

    activity: Any = factory.SubFactory(WpBpActivityFactory)


class WpBpNotificationFactory(factory.Factory):
    """Factory for creating WpBpNotification model instances.

    This factory generates test instances of the WpBpNotification model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpBpNotification


class WpPostSubTableFactory(factory.Factory):
    """Factory for creating WpPostSubTable model instances.

    This factory generates test instances of the WpPostSubTable model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.WpPostSubTable


class CoverImageFactory(factory.Factory):
    """Factory for creating CoverImage model instances.

    This factory generates test instances of the CoverImage model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.CoverImage


class ProfileImageFactory(factory.Factory):
    """Factory for creating ProfileImage model instances.

    This factory generates test instances of the ProfileImage model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.ProfileImage


class AcademicInterestFactory(factory.django.DjangoModelFactory):
    """Factory for creating AcademicInterest instances."""

    class Meta:
        model = models.AcademicInterest

    text = factory.Sequence(lambda n: f"Academic Interest {n}")


class ProfileFactory(factory.django.DjangoModelFactory):
    """Factory for creating Profile instances for testing."""

    class Meta:
        model = models.Profile

    # Required fields
    name = factory.Faker("name")
    username = factory.Sequence(lambda n: f"user_{n}")
    central_user_id = factory.Sequence(lambda n: n + 1000)

    # Optional fields with defaults
    title = factory.Faker("job")
    affiliation = factory.Faker("company")

    # Social media fields
    twitter = factory.LazyFunction(lambda: f"@{fake.user_name()}")
    github = factory.LazyFunction(lambda: fake.user_name())
    email = factory.Faker("email")
    orcid = factory.LazyFunction(
        lambda: f"0000-{fake.random_number(digits=4)}-"
        f"{fake.random_number(digits=4)}-"
        f"{fake.random_number(digits=4)}"
    )
    mastodon = factory.LazyFunction(
        lambda: f"@{fake.user_name()}@mastodon.social"
    )
    bluesky = factory.LazyFunction(lambda: f"@{fake.user_name()}.bsky.social")

    # URLs
    profile_image = factory.Faker("image_url")
    works_username = factory.Sequence(lambda n: f"works_user_{n}")

    # Rich text fields
    about_user = factory.Faker("paragraph", nb_sentences=3)
    education = factory.LazyFunction(
        lambda: f"<p>{fake.sentence()}</p><ul><li>A University, "
        f"{fake.random_element(['PhD', 'MA', 'MS', 'BA', 'BS'])}, "
        f"{fake.random_element(['2018', '2019', '2020', '2021'])}"
        f"</li></ul>"
    )

    # Text fields
    upcoming_talks = factory.LazyFunction(
        lambda: f"Upcoming talk at {fake.company()} on "
        f"{fake.future_date().strftime('%B %d, %Y')}"
    )
    projects = factory.LazyFunction(
        lambda: f"Project 1: {fake.catch_phrase()}\nProject 2: "
        f"{fake.catch_phrase()}"
    )
    publications = factory.LazyFunction(
        lambda: f"<p><strong>{fake.last_name()}, "
        f"{fake.first_name()[0]}.</strong> ({fake.year()}). "
        f"{fake.sentence()}. <em>{fake.company()}</em>, "
        f"{fake.random_int(min=1, max=20)}"
        f"({fake.random_int(min=1, max=4)}), "
        f"{fake.random_int(min=100, max=999)}-"
        f"{fake.random_int(min=1000, max=1200)}.</p>"
    )
    site = factory.Faker("url")
    institutional_or_other_affiliation = factory.Faker("company")
    figshare_url = factory.LazyFunction(
        lambda: f"https://figshare.com/{fake.user_name()}"
    )
    commons_groups = factory.LazyFunction(
        lambda: f"Group 1: {fake.word().capitalize()}\nGroup 2: "
        f"{fake.word().capitalize()}"
    )
    memberships = factory.LazyFunction(
        lambda: f"Member of {fake.company()} since {fake.year()}"
    )
    recent_commons_activity = factory.LazyFunction(
        lambda: f"Posted in {fake.word().capitalize()} group on "
        f"{fake.date_this_month().strftime('%B %d, %Y')}"
    )

    commons_sites = factory.LazyFunction(
        lambda: f"https://{fake.domain_name()}"
    )
    blog_posts = factory.LazyFunction(
        lambda: f"<p><a href='{fake.uri()}'>{fake.sentence()}</a> - "
        f"{fake.date_this_year().strftime('%B %d, %Y')}</p>"
    )
    cv = factory.LazyFunction(
        lambda: f"<h2>Education</h2><p>{fake.company()}</p>"
        f"<h2>Experience</h2><p>{fake.company()}, {fake.job()}</p>"
    )

    # Social media URLs
    facebook = factory.LazyFunction(
        lambda: f"https://facebook.com/{fake.user_name()}"
    )
    linkedin = factory.LazyFunction(
        lambda: f"https://linkedin.com/in/{fake.user_name()}"
    )
    website = factory.Faker("url")

    # Visibility settings - all default to True
    show_academic_interests = True
    show_projects = True
    show_publications = True
    show_talks = True
    show_cv = True
    show_bio = True
    show_education = True
    show_about_user = True
    show_works = True
    show_blog_posts = True
    show_commons_groups = True
    show_mastodon_feed = True

    @factory.post_generation
    def cv_file(self, create, extracted, **kwargs):
        """
        Create a dummy CV file for testing.

        Args:
            create: Whether to create the model instance
            extracted: Optional file content to use
        """
        if not create:
            return None

        return "cvs/test_cv.pdf"


class WpUserFactory(factory.Factory):
    """Factory for creating WpUser model instances.

    This factory generates test instances of the WpUser model
    for use in unit and integration tests.
    """

    user_login = ("integration_test_user",)
    user_pass = ("hashed_password",)
    user_email = ("integration@example.com",)

    class Meta:
        """Factory configuration."""

        model = models.WpUser


class UserFactory(factory.Factory):
    """Factory for creating User model instances.

    This factory generates test instances of the User model
    for use in unit and integration tests.
    """

    username = "testuser"
    email = "test@example.com"
    password = "testpass"

    class Meta:
        """Factory configuration."""

        model = User
