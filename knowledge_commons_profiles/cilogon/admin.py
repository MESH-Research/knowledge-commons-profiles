"""
Administrative views for CILogon.
"""

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.urls import reverse

from knowledge_commons_profiles.cilogon.models import EmailVerification
from knowledge_commons_profiles.cilogon.models import MaintenanceMode
from knowledge_commons_profiles.cilogon.models import ReservedUsername
from knowledge_commons_profiles.cilogon.models import SubAssociation
from knowledge_commons_profiles.cilogon.reserved_usernames import import_terms
from knowledge_commons_profiles.cilogon.reserved_usernames import (
    serialize_reserved_terms,
)
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


@admin.register(MaintenanceMode)
class MaintenanceModeAdmin(admin.ModelAdmin):
    """Singleton: the one row is edited in place; it cannot be added to or
    deleted so the toggle and its message always have a stable home."""

    list_display = ["__str__", "enabled"]

    def has_add_permission(self, request):
        return not MaintenanceMode.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReservedUsername)
class ReservedUsernameAdmin(admin.ModelAdmin):
    list_display = ["pattern", "active", "note"]
    list_filter = ["active"]
    list_editable = ["active"]
    search_fields = ["pattern", "note"]
    # Adds an "Import / export" button to the change list (see the template).
    change_list_template = "admin/cilogon/reservedusername/change_list.html"

    def get_urls(self):
        # Register the copy-and-paste import/export page alongside the standard
        # admin URLs for this model.
        urls = super().get_urls()
        custom = [
            path(
                "import-export/",
                self.admin_site.admin_view(self.import_export_view),
                name="cilogon_reservedusername_import_export",
            ),
        ]
        return custom + urls

    def import_export_view(self, request):
        """Export the current terms and import a pasted list."""
        if not self.has_change_permission(request):
            messages.error(request, "You do not have permission to do that.")
            return redirect(
                reverse("admin:cilogon_reservedusername_changelist")
            )

        if request.method == "POST":
            count = import_terms(request.POST.get("terms", ""))
            messages.success(
                request,
                f"Imported {count} reserved term(s). The list now contains "
                f"exactly what was pasted.",
            )
            return redirect(
                reverse("admin:cilogon_reservedusername_changelist")
            )

        # Export the currently active terms, ready to copy elsewhere.
        active_terms = ReservedUsername.objects.filter(
            active=True
        ).values_list("pattern", "note")
        context = {
            **self.admin_site.each_context(request),
            "title": "Import / export reserved usernames",
            "opts": self.model._meta,
            "export_text": serialize_reserved_terms(active_terms),
        }
        return TemplateResponse(
            request,
            "admin/cilogon/reservedusername/import_export.html",
            context,
        )
