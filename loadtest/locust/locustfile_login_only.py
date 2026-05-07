"""Pure login throughput stress.

Each virtual user repeatedly logs in with a random pre-seeded subject and
then logs out. Used to find the sustainable logins/sec ceiling.
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


class LoginOnlyUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def login_logout(self) -> None:
        sub = pick_subject(SUBJECTS)
        if not perform_login(self.client, sub):
            return
        perform_logout(self.client)
