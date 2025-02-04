"""
Forms for the profile app
"""

from django import forms
from models import Profile

from bleach.sanitizer import Cleaner
from bleach.linkifier import Linker


class SanitizedTextarea(forms.Textarea):
    """
    A custom form field for sanitizing and linking text input
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the SanitizedTextarea widget.

        This constructor initializes the SanitizedTextarea widget's
        configuration for the Cleaner and Linker instances. The Cleaner is set
        to strip all tags except for the ones listed here, and the Linker is
        set to linkify text.
        """
        super().__init__(*args, **kwargs)
        # Configure allowed tags, attributes, and styles
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
            ],
            attributes={"a": ["href", "title"]},
            styles=[],
            strip=True,
        )
        self.linker = Linker()

    def value_from_datadict(self, data, files, name):
        value = super().value_from_datadict(data, files, name)
        if value:
            # Clean the input and automatically create links
            value = self.cleaner.clean(value)
            value = self.linker.linkify(value)
        return value


class ProfileForm(forms.ModelForm):
    """
    A form for a user profile
    """

    class Meta:
        """
        Meta class for the ProfileForm
        """

        model = Profile
        fields = [
            "name",
            "title",
            "affiliation",
            "twitter",
            "github",
            "orcid",
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
            "cv",
            "facebook",
            "linkedin",
            "website",
        ]
        widgets = {
            "about_user": forms.Textarea(attrs={"rows": 4}),
            "education": forms.Textarea(attrs={"rows": 4}),
            "upcoming_talks": forms.Textarea(attrs={"rows": 4}),
            "projects": forms.Textarea(attrs={"rows": 4}),
            "publications": forms.Textarea(attrs={"rows": 4}),
            "institutional_or_other_affiliation": forms.Textarea(
                attrs={"rows": 4}
            ),
            "figshare_url": forms.URLInput(),
            "memberships": forms.Textarea(attrs={"rows": 4}),
            "blog_posts": forms.Textarea(attrs={"rows": 4}),
            "cv": forms.Textarea(attrs={"rows": 4}),
            "facebook": forms.URLInput(),
            "linkedin": forms.URLInput(),
            "website": forms.URLInput(),
            "profile_image": forms.URLInput(),
        }
