"""
Administrative views for CILogon.
"""

from django import forms
from django.contrib import admin

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import ReservedUsername
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.newprofile.models import Profile


class ProfileChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Profile):
        return obj.admin_display()


@admin.register(SubAssociation)
class SubAssocationAdmin(admin.ModelAdmin):
    autocomplete_fields = ["profile"]
    search_fields = [
        "profile__username",
        "profile__email",
        "profile__name",
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "profile":
            kwargs["form_class"] = ProfileChoiceField

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(EmailVerification)


@admin.register(ReservedUsername)
class ReservedUsernameAdmin(admin.ModelAdmin):
    list_display = ["pattern", "active", "note"]
    list_filter = ["active"]
    list_editable = ["active"]
    search_fields = ["pattern", "note"]
