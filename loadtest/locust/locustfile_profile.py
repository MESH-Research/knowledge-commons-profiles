"""Profile-page workload.

A real browser loading `/members/<username>/` triggers eight HTTP requests:
the page shell plus seven HTMX fragments that fill in the sidebar widgets,
images, and works/blog/feed panels. This locustfile reproduces that fan-out
per VU iteration so the per-hop latency for each fragment shows up
separately in the Locust stats table.

Anonymous traffic by default — the profile page and all its HTMX fragments
are unauthenticated read paths. Set `PROFILE_REQUIRE_LOGIN=1` to log every
VU in via the OIDC flow first, which exercises the authenticated request
path (cilogon AutoRefreshTokenMiddleware, session lookup, etc.).
"""

from __future__ import annotations

import os

from _common import LOADTEST_INSECURE
from _common import load_subjects
from _common import perform_login
from _common import pick_subject
from locust import between
from locust import task
from locust.contrib.fasthttp import FastHttpUser

SUBJECTS = load_subjects()
REQUIRE_LOGIN = os.environ.get("PROFILE_REQUIRE_LOGIN", "0") == "1"

# HTMX fragments loaded after the profile shell renders. Each one is a
# separate GET against /htmx/<fragment>/<username>/.
PROFILE_HTMX_FRAGMENTS = (
    "profile-info",
    "cover-image",
    "profile-image",
    "mysql-data",
    "works-deposits",
    "blog-posts",
    "mastodon-feed",
)


class ProfilePageUser(FastHttpUser):
    insecure = LOADTEST_INSECURE
    # Reading time between page views — a real visitor scans a profile for
    # a few seconds before clicking through to the next.
    wait_time = between(2, 8)

    def on_start(self) -> None:
        self.subject = pick_subject(SUBJECTS)
        if REQUIRE_LOGIN:
            perform_login(self.client, self.subject)

    @task
    def view_profile_page(self) -> None:
        """Load one profile's shell + all its HTMX fragments."""
        username = pick_subject(SUBJECTS)
        self.client.get(
            f"/members/{username}/",
            name="profile shell",
        )
        for fragment in PROFILE_HTMX_FRAGMENTS:
            self.client.get(
                f"/htmx/{fragment}/{username}/",
                name=f"htmx {fragment}",
                headers={"HX-Request": "true"},
            )
