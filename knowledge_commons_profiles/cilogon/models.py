from django.db import models

from knowledge_commons_profiles.newprofile.models import Profile


class SubAssociation(models.Model):
    """
    A model that associates a CI Logon sub with a profile
    """

    sub = models.CharField(max_length=255)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.sub


class TokenUserAgentAssociations(models.Model):
    """
    Associates the most recent token with a user agent and an app, allowing
    single-service logout
    """

    user_agent = models.CharField(max_length=255)
    token = models.TextField()
    app = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.app} - {self.token} - {self.user_agent}"
