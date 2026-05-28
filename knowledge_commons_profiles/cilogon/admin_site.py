from django.contrib import admin
from django.contrib.admin.views.autocomplete import AutocompleteJsonView

from knowledge_commons_profiles.newprofile.models import Profile


class CustomAutocompleteJsonView(AutocompleteJsonView):
    def serialize_result(self, obj, to_field_name):
        result = super().serialize_result(obj, to_field_name)

        if isinstance(obj, Profile):
            result["text"] = obj.admin_display()

        return result


class CustomAdminSite(admin.AdminSite):
    def autocomplete_view(self, request):
        return CustomAutocompleteJsonView.as_view(admin_site=self)(request)
