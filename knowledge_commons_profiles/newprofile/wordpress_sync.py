"""WordPress synchronization for profile data (#392)."""

import requests  # noqa: F401


def sync_avatar_to_wordpress(username: str, image_url: str) -> bool:
    """Sync the user's avatar to WordPress via REST API."""
    raise NotImplementedError
