"""
Administrative views for Profiles.
"""

from django.contrib import admin

from knowledge_commons_profiles.newprofile.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["username", "email", "name"]
    list_display = ["username", "name", "email"]
