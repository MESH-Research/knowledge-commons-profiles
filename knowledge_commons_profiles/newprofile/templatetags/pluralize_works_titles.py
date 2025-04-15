"""
Get the plural form of a Works heading
"""

from django import template

from knowledge_commons_profiles.newprofile.works import PLURALS

register = template.Library()


@register.filter
def pluralize_work_heading(heading):
    """
    Get the plural form of a Works heading
    """

    return PLURALS[heading] if heading in PLURALS else heading + "s"
