"""
Utility functions
"""


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
