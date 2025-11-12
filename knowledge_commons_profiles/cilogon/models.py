import datetime
import logging

from django.conf import settings
from django.db import models

from knowledge_commons_profiles.newprofile.models import Profile

logger = logging.getLogger(__name__)


class SubAssociation(models.Model):
    """
    A model that associates a CI Logon sub with a profile
    """

    sub = models.CharField(
        max_length=255, verbose_name="CI Logon ID", unique=True
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        null=True,
        verbose_name="Associated KC Profile",
    )

    idp_name = models.TextField(verbose_name="IDP Name", blank=True, null=True)

    class Meta:
        verbose_name = "CI Logon Association"
        verbose_name_plural = "CI Logon Associations"

    def __str__(self):
        return self.profile.username + " (" + self.sub + ")"


class TokenUserAgentAssociations(models.Model):
    """
    Associates a token with a user agent and an app, allowing
    single-service logout
    """

    user_agent = models.CharField(max_length=255)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    app = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255, default="")

    # auto date field updated at time of creation
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return (
            f"{self.app} - [REFRESH] {self.refresh_token} [ACCESS] "
            f"{self.access_token} for {self.user_agent} "
            f"({self.created_at})"
        )


class EmailVerification(models.Model):
    """
    A model that potentially associates a CI Logon sub with a profile
    """

    sub: str = models.CharField(max_length=255)
    secret_uuid: str = models.CharField(max_length=255)
    profile: Profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True
    )
    created_at: datetime.datetime = models.DateTimeField(
        auto_now_add=True, blank=True, null=True
    )

    def __str__(self):
        return str(self.profile) + " (" + self.sub + ")"

    @classmethod
    def garbage_collect(cls):
        """
        Garbage collect this object if it is older than the configured limit
        """
        verifications = EmailVerification.objects.filter(
            created_at__lt=datetime.datetime.now(tz=datetime.UTC)
            - datetime.timedelta(hours=settings.VERIFICATION_LIMIT_HOURS)
        )

        count = verifications.count()

        if count > 0:
            msg = f"Garbage collected {count} email verifications"
            logger.info(msg)

            # delete the verifications
            verifications.delete()
