"""
Forms for the profile app
"""

from bleach.linkifier import Linker
from bleach.sanitizer import Cleaner
from django import forms
from django_select2.forms import ModelSelect2MultipleWidget
from tinymce.widgets import TinyMCE

from newprofile.models import Profile, AcademicInterest

from django_select2 import forms as s2forms


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


class ProfileForm(forms.ModelForm):

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
            "academic_interests": ModelSelect2MultipleWidget(
                model=AcademicInterest,
                search_fields=["text"],
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Start typing an interest...",
                    "data-close-on-select": "false",
                    "style": "width:100%;",
                },
            ),
            "show_works": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"}
            ),
            "show_cv": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"}
            ),
            "show_blog_posts": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"}
            ),
            "show_mastodon_feed": forms.CheckboxInput(
                attrs={"style": "display: inline-block; float:right;"}
            ),
            "about_user": SanitizedTinyMCE(
                attrs={
                    "cols": 80,
                    "rows": 30,
                },
                mce_attrs={
                    "menubar": True,
                    "plugins": [
                        "advlist",
                        "autolink",
                        "lists",
                        "link",
                        "image",
                        "charmap",
                        "preview",
                        "anchor",
                        "searchreplace",
                        "visualblocks",
                        "fullscreen",
                        "insertdatetime",
                        "table",
                        "code",
                    ],
                    "toolbar": """
                    undo redo | formatselect | bold italic | 
                    alignleft aligncenter alignright | 
                    bullist numlist | link image | removeformat | code
                """,
                    "width": "100%",
                },
            ),
            "education": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "projects": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
            "publications": SanitizedTinyMCE(attrs={"cols": 80, "rows": 20}),
        }
