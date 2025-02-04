"""
Forms for the profile app
"""

from django import forms
from models import Profile

from bleach.sanitizer import Cleaner
from bleach.linkifier import Linker

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Div, Field, Submit, HTML
from crispy_forms.bootstrap import TabHolder, Tab


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
            "cv_from_file",
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
            "facebook": forms.URLInput(),
            "linkedin": forms.URLInput(),
            "website": forms.URLInput(),
            "profile_image": forms.URLInput(),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["cv"].widget.attrs.update(
                {"accept": ".pdf,.doc,.docx"}  # Limit accepted file types
            )

            # layout

            self.helper = FormHelper()
            self.helper.form_method = "post"
            self.helper.form_class = "form-horizontal"
            self.helper.form_tag = True
            self.helper.form_enctype = "multipart/form-data"

            self.helper.layout = Layout(
                TabHolder(
                    Tab(
                        "Basic Info",
                        Fieldset(
                            "Personal Information",
                            Div(
                                Div("name", css_class="col-md-6"),
                                Div("username", css_class="col-md-6"),
                                css_class="row",
                            ),
                            Div(
                                Div("title", css_class="col-md-6"),
                                Div("affiliation", css_class="col-md-6"),
                                css_class="row",
                            ),
                            "profile_image",
                            Field("about_user", rows=4),
                            css_class="mb-4",
                        ),
                        Fieldset(
                            "Education & Academic Interests",
                            Field("education", rows=4),
                            "academic_interests",
                            css_class="mb-4",
                        ),
                    ),
                    Tab(
                        "Professional",
                        Fieldset(
                            "Professional Information",
                            Field(
                                "institutional_or_other_affiliation", rows=3
                            ),
                            Field("projects", rows=4),
                            Field("publications", rows=4),
                            Field("upcoming_talks", rows=4),
                            Field("cv", css_class="mb-3"),
                            css_class="mb-4",
                        ),
                    ),
                    Tab(
                        "Social & Contact",
                        Fieldset(
                            "Contact Information",
                            Div(
                                Div("email", css_class="col-md-6"),
                                Div("website", css_class="col-md-6"),
                                css_class="row",
                            ),
                        ),
                        Fieldset(
                            "Social Media",
                            Div(
                                Div("twitter", css_class="col-md-4"),
                                Div("mastodon", css_class="col-md-4"),
                                Div("github", css_class="col-md-4"),
                                css_class="row",
                            ),
                            Div(
                                Div("facebook", css_class="col-md-4"),
                                Div("linkedin", css_class="col-md-4"),
                                Div("orcid", css_class="col-md-4"),
                                css_class="row",
                            ),
                        ),
                    ),
                    Tab(
                        "Commons & Community",
                        Fieldset(
                            "Commons Information",
                            "works_username",
                            Field("commons_groups", rows=3),
                            Field("commons_sites", rows=3),
                            Field("recent_commons_activity", rows=3),
                            Field("memberships", rows=3),
                            "figshare_url",
                            Field("blog_posts", rows=3),
                        ),
                    ),
                ),
                Div(
                    Submit(
                        "submit", "Save Profile", css_class="btn btn-primary"
                    ),
                    HTML(
                        "<a href='{% url \"profile_view\" %}' class='btn btn-secondary ms-2'>Cancel</a>"
                    ),
                    css_class="mt-4",
                ),
            )
