"""Same-user contention stress.

Pins every VU to a small pool of subjects (default 10) and hammers the
login path. Validates the `select_for_update().get_or_create()` pattern in
`cilogon/oauth.py:find_user_and_login` under real load: zero IntegrityError
5xx, exactly N User rows for N pool subjects after the run.
"""

from __future__ import annotations

import os
import random

from _common import load_subjects
from _common import perform_login
from _common import perform_logout
from locust import HttpUser
from locust import between
from locust import task

POOL_SIZE = int(os.environ.get("LOADTEST_SAME_USER_POOL", "10"))
SUBJECTS = load_subjects()[:POOL_SIZE]
if not SUBJECTS:
    msg = "No subjects to pool. Seed identities first."
    raise RuntimeError(msg)


class SameUserContentionUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def hammer_login(self) -> None:
        sub = random.choice(SUBJECTS)  # noqa: S311
        if perform_login(self.client, sub):
            perform_logout(self.client)
