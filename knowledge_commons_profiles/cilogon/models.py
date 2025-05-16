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
