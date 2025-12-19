"""
Forms for the profile app
"""

from bleach.linkifier import Linker
from bleach.sanitizer import Cleaner
from django import forms
from django.core.exceptions import ValidationError
from django_select2.forms import ModelSelect2TagWidget
from tinymce.widgets import TinyMCE

from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile


class SanitizedTinyMCE(TinyMCE):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaner = Cleaner(
            tags=[
                "p",
                "b",
                "i",
                "u",
                "em",
                "strong",
                "a",
                "ul",
                "ol",
                "li",
                "br",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "table",
                "tbody",
                "thead",
                "tr",
                "td",
                "th",
                "img",
            ],
            attributes={
                "a": ["href", "title"],
                "img": ["src", "alt", "width", "height"],
                "td": ["colspan", "rowspan"],
                "th": ["colspan", "rowspan"],
            },
            strip=True,
        )
        self.linker = Linker()

    def value_from_datadict(self, data, files, name):
        value = super().value_from_datadict(data, files, name)

        if value:
            value = self.cleaner.clean(value)
            value = self.linker.linkify(value)

        return value


class AcademicInterestsSelect2TagWidget(ModelSelect2TagWidget):
    queryset = AcademicInterest.objects.all()


class ProfileForm(forms.ModelForm):
    cv_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".pdf,.doc,.docx",
                "class": "form-control",
            }
        ),
        help_text="Upload your CV (PDF, DOC, or DOCX). "
        'Check "Clear" to remove your current CV.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert newlines to <br> tags if instance exists
        if self.instance.pk and self.instance.about_user:
            self.initial["about_user"] = self.instance.about_user

        if self.instance.pk and self.instance.education:
            self.initial["education"] = self.instance.education

        if self.instance.pk and self.instance.upcoming_talks:
            self.initial["upcoming_talks"] = self.instance.upcoming_talks

        if self.instance.pk and self.instance.projects:
            self.initial["projects"] = self.instance.projects

        if self.instance.pk and self.instance.publications:
            self.initial["publications"] = self.instance.publications

    class Meta:
        model = Profile
        fields = [
            "name",
            "title",
            "twitter",
            "github",
            "orcid",
            "cv_file",
            "mastodon",
            "academic_interests",
            "about_user",
            "education",
            "upcoming_talks",
            "projects",
            "publications",
            "institutional_or_other_affiliation",
            "figshare_url",
            "memberships",
            "facebook",
            "linkedin",
            "website",
            "bluesky",
            "cv_file",
            "show_works",
            "show_cv",
            "show_blog_posts",
            "show_mastodon_feed",
            "show_commons_groups",
            "show_projects",
            "show_publications",
            "show_education",
            "show_academic_interests",
            "show_recent_activity",
            "show_commons_sites",
            "academic_interests",
            "reference_style",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"style": "width:75%; line-height:1.6;"}
            ),
            "name": forms.TextInput(
                attrs={"style": "width:75%; line-height:1.6;"}
            ),
            "institutional_or_other_affiliation": forms.TextInput(
                attrs={"style": "width:75%; line-height:1.6;"}
            ),
            "website": forms.TextInput(
                attrs={"style": "width:100%; line-height:1.6;"}
            ),
            "cv_file": forms.FileInput(attrs={"style": "width:100%;"}),
            "twitter": forms.TextInput(
                attrs={"style": "width:200px; line-height:1.6;"}
            ),
            "mastodon": forms.TextInput(
                attrs={"style": "width:200px; line-height:1.6;"}
            ),
            "orcid": forms.TextInput(
                attrs={"style": "width:200px; line-height:1.6;"}
            ),
            "bluesky": forms.TextInput(
                attrs={"style": "width:200px; line-height:1.6;"}
            ),
            "academic_interests": AcademicInterestsSelect2TagWidget(
                model=AcademicInterest,
                search_fields=["text__icontains"],
                allowClear=True,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Start typing an interest...",
                    "data-close-on-select": "false",
                    "data-token-separators": "[',']",
                    "style": "width:100%;",
                },
                build_attrs={},
            ),
            "show_works": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_cv": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right;"
                    "margin-top:-4em;"
                },
            ),
            "show_blog_posts": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_mastodon_feed": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_commons_groups": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_projects": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_publications": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_education": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_academic_interests": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_recent_activity": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "show_commons_sites": forms.CheckboxInput(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-4em;"
                },
            ),
            "reference_style": forms.Select(
                attrs={
                    "style": "display: inline-block; float:right; "
                    "margin-top:-3.9em; margin-right: 2em;",
                    "hx-trigger": "change",
                    "hx-post": "/works-deposits-edit/",  # NOTE: this is a hack
                    "hx-swap": "none",
                },
            ),
            "projects": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "publications": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "memberships": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "about_user": SanitizedTinyMCE(
                attrs={"cols": 80, "rows": 20, "promotion": "false"}
            ),
            "education": SanitizedTinyMCE(
                attrs={"cols": 80, "rows": 20, "promotion": "false"}
            ),
        }

    def clean_cv_file(self):
        cv_file = self.cleaned_data.get("cv_file")
        if cv_file:
            # Check file size (10 MB limit)
            if cv_file.size > 10 * 1024 * 1024:
                msg = "File size must not exceed 10 MB."
                raise ValidationError(msg)

            # Check file extension
            allowed_extensions = ["pdf", "doc", "docx"]
            file_ext = cv_file.name.split(".")[-1].lower()
            if file_ext not in allowed_extensions:
                msg = (
                    f"File type '{file_ext}' is not allowed. Use PDF, "
                    f"DOC, or DOCX."
                )
                raise ValidationError(msg)

        return cv_file


class AvatarUploadForm(forms.Form):
    """
    Form for uploading an avatar or cover image
    """

    image = forms.ImageField(required=True)
