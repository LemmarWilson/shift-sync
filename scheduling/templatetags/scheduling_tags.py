"""
Custom template tags and filters for the scheduling app.

This module provides template utilities for accessing dictionary values
with dynamic keys and other scheduling-specific template operations.
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key in Django templates.

    This filter is essential for accessing dictionary values when the key
    is a variable (e.g., a date object) rather than a string literal.

    Usage:
        {{ my_dict|get_item:key_variable }}

    Args:
        dictionary: The dictionary to look up. Can be None.
        key: The key to retrieve.

    Returns:
        The value for the key, or an empty list if not found or dict is None.

    Example:
        {% with shifts=shifts_by_date|get_item:day_date %}
            {% for shift in shifts %}...{% endfor %}
        {% endwith %}
    """
    if dictionary is None:
        return []
    return dictionary.get(key, [])
