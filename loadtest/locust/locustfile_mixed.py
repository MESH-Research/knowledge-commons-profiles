"""95/5 mixed-traffic stress.

Each VU logs in once on `on_start`, then spends its life browsing — viewing
its own profile, viewing other profiles, and occasionally logging out and
back in to keep ~5% of traffic on the login path.
"""

from __future__ import annotations

from _common import load_subjects
from _common import perform_login
from _common import perform_logout
from _common import pick_subject
from locust import HttpUser
from locust import between
from locust import task

SUBJECTS = load_subjects()


class MixedUser(HttpUser):
    wait_time = between(3, 10)

    def on_start(self) -> None:
        self.subject = pick_subject(SUBJECTS)
        perform_login(self.client, self.subject)

    @task(10)
    def view_own_profile(self) -> None:
        self.client.get(
            f"/members/{self.subject}/",
            name="profile view (own)",
        )

    @task(3)
    def view_other_profile(self) -> None:
        other = pick_subject(SUBJECTS)
        self.client.get(
            f"/members/{other}/",
            name="profile view (other)",
        )

    @task(2)
    def view_my_profile_dashboard(self) -> None:
        self.client.get("/my-profile/", name="/my-profile")

    @task(1)
    def relogin(self) -> None:
        if perform_logout(self.client, name_prefix="re "):
            perform_login(self.client, self.subject, name_prefix="re ")
