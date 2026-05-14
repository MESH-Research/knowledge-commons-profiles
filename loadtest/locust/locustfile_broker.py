"""Cross-app broker SSO stress.

Drives `/login/?return_to=...&final_redirect=...`. The IDMS stores the
return_to in the Django session, runs the OIDC dance, then redirects to the
broker URL with an encrypted token. We then exercise the back-channel
verification via POST /broker/verify-nonce/ with a static bearer.

Configure via env vars:
  BROKER_RETURN_TO        Allowed return_to URL (default: dummy on hcommons-test.org)
  BROKER_FINAL_REDIRECT   Optional final redirect carried alongside return_to.
  STATIC_API_BEARER       Must match the IDMS's setting for verify-nonce to pass.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qs
from urllib.parse import urlparse

from _common import LOADTEST_INSECURE
from _common import callback_path_with_query
from _common import inject_login_hint
from _common import load_subjects
from _common import pick_subject
from locust import between
from locust import task
from locust.contrib.fasthttp import FastHttpUser

SUBJECTS = load_subjects()
RETURN_TO = os.environ.get(
    "BROKER_RETURN_TO",
    "https://wordpress.hcommons-test.org/wp-json/idms/broker-callback",
)
FINAL_REDIRECT = os.environ.get("BROKER_FINAL_REDIRECT", "")
STATIC_API_BEARER = os.environ.get("STATIC_API_BEARER", "")


class BrokerUser(FastHttpUser):
    insecure = LOADTEST_INSECURE
    wait_time = between(1, 4)

    @task
    def broker_login(self) -> None:
        sub = pick_subject(SUBJECTS)

        # 1. /login/?return_to=...&final_redirect=...
        params = {"return_to": RETURN_TO}
        if FINAL_REDIRECT:
            params["final_redirect"] = FINAL_REDIRECT
        r = self.client.get(
            "/login/",
            params=params,
            allow_redirects=False,
            name="01 /login (broker)",
        )
        if r.status_code != 302:
            return
        authorize_url = inject_login_hint(r.headers.get("Location", ""), sub)

        # 2. mock /authorize
        r = self.client.get(
            authorize_url,
            allow_redirects=False,
            name="02 IdP /authorize",
        )
        if r.status_code != 302:
            return
        callback_url = r.headers.get("Location", "")

        # 3. /cilogon/callback/ — should now redirect to the broker URL with
        #    an encrypted token query param.
        r = self.client.get(
            callback_path_with_query(callback_url),
            allow_redirects=False,
            name="03 /cilogon/callback (broker)",
        )
        if r.status_code != 302:
            return
        broker_redirect = r.headers.get("Location", "")
        if not broker_redirect:
            return

        # 4. Back-channel nonce verification (only meaningful if a nonce-like
        #    parameter is present and STATIC_API_BEARER is configured).
        nonce = _extract_nonce(broker_redirect)
        if not nonce or not STATIC_API_BEARER:
            return

        self.client.post(
            "/broker/verify-nonce/",
            json={"nonce": nonce},
            headers={"Authorization": f"Bearer {STATIC_API_BEARER}"},
            name="04 /broker/verify-nonce",
        )


def _extract_nonce(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("nonce", "broker_nonce", "kc_nonce"):
        if qs.get(key):
            return qs[key][0]
    return None
