"""
Access a dynamic dictionary in a template
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary
    """
    return dictionary.get(key)
