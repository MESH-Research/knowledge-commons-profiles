"""
Helpers for building SOQL safely.
"""


def soql_quote(value: str) -> str:
    """
    Return ``value`` as a quoted SOQL string literal with the characters
    that would otherwise terminate the literal escaped.

    SOQL string literals use backslash escapes, so a backslash and a
    single quote inside the value are escaped as ``\\\\`` and ``\\'``.
    """
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"
