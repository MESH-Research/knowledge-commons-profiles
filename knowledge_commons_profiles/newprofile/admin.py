"""
Administrative views for Profiles.
"""

from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html

from knowledge_commons_profiles.newprofile.models import Badge
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import ProfileBadge


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["username", "email", "name"]
    list_display = ["username", "name", "email"]


class ProfileBadgeInline(admin.TabularInline):
    model = ProfileBadge
    autocomplete_fields = ["profile"]
    readonly_fields = ["awarded_at"]
    extra = 1


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["thumbnail", "title", "order", "award_count"]
    list_display_links = ["thumbnail", "title"]
    list_editable = ["order"]
    search_fields = ["title"]
    inlines = [ProfileBadgeInline]
    change_form_template = "admin/newprofile/badge/change_form.html"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_award_count=Count("profiles"))
        )

    @admin.display(description="Image")
    def thumbnail(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" alt="{}" style="height:40px;width:40px;'
            'object-fit:contain;" />',
            obj.image.url,
            obj.alt_text,
        )

    @admin.display(description="Awarded to", ordering="_award_count")
    def award_count(self, obj):
        return obj._award_count

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:badge_id>/mass-award/",
                self.admin_site.admin_view(self.mass_award_view),
                name="newprofile_badge_mass_award",
            ),
        ]
        return custom + urls

    def mass_award_view(self, request, badge_id):
        """
        Mass award or remove a badge for a comma-separated username list.
        """
        badge = get_object_or_404(Badge, pk=badge_id)

        if request.method == "POST":
            usernames = [
                username.strip()
                for username in request.POST.get("usernames", "").split(",")
                if username.strip()
            ]
            action = request.POST.get("action", "award")

            profiles = list(Profile.objects.filter(username__in=usernames))
            found = {profile.username.lower() for profile in profiles}
            unknown = [
                username
                for username in usernames
                if username.lower() not in found
            ]

            if action == "remove":
                removed, _ = ProfileBadge.objects.filter(
                    badge=badge, profile__in=profiles
                ).delete()
                messages.success(
                    request,
                    f'Removed "{badge.title}" from {removed} profile(s).',
                )
            else:
                awarded = 0
                for profile in profiles:
                    _, created = ProfileBadge.objects.get_or_create(
                        badge=badge, profile=profile
                    )
                    awarded += int(created)
                skipped = len(profiles) - awarded
                message = (
                    f'Awarded "{badge.title}" to {awarded} profile(s).'
                )
                if skipped:
                    message += f" {skipped} already held it."
                messages.success(request, message)

            if unknown:
                messages.warning(
                    request,
                    "Unknown username(s): " + ", ".join(unknown),
                )

            return redirect(
                reverse(
                    "admin:newprofile_badge_change",
                    args=[badge.pk],
                )
            )

        return render(
            request,
            "admin/newprofile/badge/mass_award.html",
            {
                **self.admin_site.each_context(request),
                "badge": badge,
                "opts": self.model._meta,
                "title": f"Mass award or remove: {badge.title}",
            },
        )
