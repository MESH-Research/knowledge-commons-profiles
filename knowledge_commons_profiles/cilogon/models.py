import datetime

from django.db import models

from knowledge_commons_profiles.newprofile.models import Profile


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
