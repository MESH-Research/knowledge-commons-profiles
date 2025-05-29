"""
Utility functions
"""

from nameparser import HumanName

from knowledge_commons_profiles.newprofile.models import Profile


def build_metadata(authed, error=None):
    """
    Build the metadata for the response
    """

    return_dict = {
        "meta": {
            "authorized": authed,
        }
    }

    if error:
        return_dict["meta"]["error"] = error

    return return_dict


def get_first_name(obj: Profile, logger) -> str:
    """Extract and format the first name"""
    if not obj.name:
        return ""

    try:
        name = HumanName(obj.name)
        # Include middle if present
        parts = [name.first, name.middle]
        return " ".join(p for p in parts if p).strip()
    except Exception as e:  # noqa: BLE001
        message = f"Failed to parse first name for {obj.username}: {e}"
        logger.warning(message)
        return ""


def get_last_name(obj: Profile, logger) -> str:
    """Extract and format the last name"""
    if not obj.name:
        return ""

    try:
        return HumanName(obj.name).last or ""
    except Exception as e:  # noqa: BLE001
        message = f"Failed to parse last name for {obj.username}: {e}"
        logger.warning(message)
        return ""
