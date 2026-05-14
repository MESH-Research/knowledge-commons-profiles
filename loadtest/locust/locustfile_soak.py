"""Long-running soak.

Same shape as the mixed-traffic scenario but tuned for steady moderate
load over hours. Designed to surface session-table growth (sessions are
DB-backed in this codebase), Redis cache growth, TokenUserAgentAssociations
growth, and any DB connection leak.
"""

from __future__ import annotations

from _common import LOADTEST_INSECURE
from _common import load_subjects
from _common import perform_login
from _common import perform_logout
from _common import pick_subject
from locust import between
from locust import task
from locust.contrib.fasthttp import FastHttpUser

SUBJECTS = load_subjects()


class SoakUser(FastHttpUser):
    insecure = LOADTEST_INSECURE
    wait_time = between(15, 45)

    def on_start(self) -> None:
        self.subject = pick_subject(SUBJECTS)
        perform_login(self.client, self.subject)

    @task(20)
    def view_own_profile(self) -> None:
        self.client.get(
            f"/members/{self.subject}/",
            name="profile view (own)",
        )

    @task(5)
    def view_other_profile(self) -> None:
        self.client.get(
            f"/members/{pick_subject(SUBJECTS)}/",
            name="profile view (other)",
        )

    @task(2)
    def view_my_profile_dashboard(self) -> None:
        self.client.get("/my-profile/", name="/my-profile")

    @task(1)
    def relogin(self) -> None:
        if perform_logout(self.client, name_prefix="re "):
            perform_login(self.client, self.subject, name_prefix="re ")
