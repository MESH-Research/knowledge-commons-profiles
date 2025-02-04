"""
Forms for the profile app
"""

from django import forms
from newprofile.models import Profile

from bleach.sanitizer import Cleaner
from bleach.linkifier import Linker

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Div, Field, Submit, HTML
from crispy_forms.bootstrap import TabHolder, Tab
from django_bleach.models import BleachField

from tinymce.widgets import TinyMCE


from django import forms
from bleach.sanitizer import Cleaner
from bleach.linkifier import Linker
from tinymce.widgets import TinyMCE


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
        ]
        widgets = {
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
