"""Factory classes for knowledge commons profile models.

This module provides factory classes for creating test instances of models
in the knowledge_commons_profiles application.
"""

from typing import Any

import factory

from knowledge_commons_profiles.newprofile import models


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


class ProfileFactory(factory.Factory):
    """Factory for creating Profile model instances.

    This factory generates test instances of the Profile model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.Profile


class AcademicInterestFactory(factory.Factory):
    """Factory for creating AcademicInterest model instances.

    This factory generates test instances of the AcademicInterest model
    for use in unit and integration tests.
    """

    class Meta:
        """Factory configuration."""

        model = models.AcademicInterest
