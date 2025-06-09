"""
Administrative views for CILogon.
"""

from django.contrib import admin

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import SubAssociation


@admin.register(SubAssociation)
class SubAssocationAdmin(admin.ModelAdmin):
    autocomplete_fields = ["profile"]


admin.site.register(EmailVerification)
