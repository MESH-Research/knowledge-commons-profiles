"""
Forms for the profile app
"""

from bleach import clean
from bleach.linkifier import Linker
from bleach.sanitizer import Cleaner
from django import forms
from django.utils.html import linebreaks
from django_bleach.forms import BleachField
from django_select2.forms import ModelSelect2TagWidget
from tinymce.widgets import TinyMCE

from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile


class ProfileBleachFormField(BleachField):
    """
    A subclass of BleachField that uses the TinyMCE widget
    """

    widget = TinyMCE

    def to_python(self, value):
        if value in self.empty_values:
            return self.empty_value
        return clean(value, **self.bleach_options)


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert newlines to <br> tags if instance exists
        if self.instance.pk and self.instance.about_user:
            self.initial["about_user"] = linebreaks(self.instance.about_user)

        if self.instance.pk and self.instance.education:
            self.initial["education"] = linebreaks(self.instance.education)

        if self.instance.pk and self.instance.upcoming_talks:
            self.initial["upcoming_talks"] = linebreaks(
                self.instance.upcoming_talks,
            )

        if self.instance.pk and self.instance.projects:
            self.initial["projects"] = linebreaks(self.instance.projects)

        if self.instance.pk and self.instance.publications:
            self.initial["publications"] = linebreaks(
                self.instance.publications,
            )

    class Meta:
        model = Profile
        fields = [
            "name",
            "title",
            "affiliation",
            "twitter",
            "github",
            "orcid",
            "cv_file",
            "mastodon",
            "profile_image",
            "works_username",
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
            "academic_interests",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"style": "width:100%"}),
            "name": forms.TextInput(attrs={"style": "width:100%"}),
            "affiliation": forms.TextInput(attrs={"style": "width:100%"}),
            "website": forms.TextInput(attrs={"style": "width:100%"}),
            "cv_file": forms.FileInput(attrs={"style": "width:100%;"}),
            "twitter": forms.TextInput(attrs={"style": "width:130px"}),
            "mastodon": forms.TextInput(attrs={"style": "width:130px"}),
            "orcid": forms.TextInput(attrs={"style": "width:130px"}),
            "bluesky": forms.TextInput(attrs={"style": "width:130px"}),
            "academic_interests": AcademicInterestsSelect2TagWidget(
                model=AcademicInterest,
                search_fields=["text__icontains"],
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
                attrs={"style": "display: inline-block; float:right;"},
            ),
            "show_cv": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"},
            ),
            "show_blog_posts": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"},
            ),
            "show_mastodon_feed": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"},
            ),
            "projects": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "publications": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "memberships": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
        }
