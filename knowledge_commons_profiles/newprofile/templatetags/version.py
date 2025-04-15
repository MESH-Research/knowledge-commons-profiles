"""
Return the application version
"""

from django import template

from knowledge_commons_profiles.__version__ import VERSION

register = template.Library()


@register.simple_tag(name="version")
def version():
    """
    Get the application version
    """

    return VERSION
