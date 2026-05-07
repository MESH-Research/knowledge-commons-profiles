"""Shared helpers for the IDMS Locust scripts.

Drives the real CILogon-shaped OIDC flow against the mock IdP. The tasks
elsewhere import the helpers from here so the four scenarios stay
consistent in how they name hops, harvest CSRF, and parse redirects.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from urllib.parse import urlparse

# --- TLS verification toggle ---------------------------------------------
# Locust's HttpUser.client is a requests.Session subclass. By default we
# disable certificate verification so the suite can hit a local IDMS with
# a self-signed dev cert without exploding. Set LOADTEST_SSL_VERIFY=1 to
# re-enable verification (the right setting for any non-dev target).
LOADTEST_SSL_VERIFY = os.environ.get("LOADTEST_SSL_VERIFY", "0") == "1"

if not LOADTEST_SSL_VERIFY:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        from locust.clients import HttpSession

        _orig_session_init = HttpSession.__init__

        def _patched_session_init(self, *args, **kwargs):
            _orig_session_init(self, *args, **kwargs)
            self.verify = False

        HttpSession.__init__ = _patched_session_init
    except ImportError:  # pragma: no cover — only matters when locust is installed
        pass

DEFAULT_SUBJECTS_PATH = Path(
    os.environ.get("LOADTEST_SUBJECTS", "/tmp/loadtest_subjects.txt")  # noqa: S108
)
MOCK_IDP_BASE = os.environ.get("MOCK_IDP_BASE", "http://mock-oidc:8080").rstrip(
    "/"
)


def load_subjects(path: Path = DEFAULT_SUBJECTS_PATH) -> list[str]:
    """Load the seeded subject list. Aborts loudly if missing."""
    if not path.exists():
        msg = (
            f"Subjects file not found: {path}. Run "
            "`manage.py seed_loadtest_identities --count N` against the test "
            "deployment first, then mount the resulting file into the locust "
            "containers (volume) at the same path."
        )
        raise FileNotFoundError(msg)
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def pick_subject(subjects: list[str]) -> str:
    return random.choice(subjects)  # noqa: S311


def inject_login_hint(authorize_url: str, sub: str) -> str:
    """Append `login_hint=<sub>` so the mock IdP knows which user to issue."""
    sep = "&" if "?" in authorize_url else "?"
    return f"{authorize_url}{sep}login_hint={sub}"


def callback_path_with_query(callback_url: str) -> str:
    """Strip the scheme/host from the callback URL the mock returns."""
    parsed = urlparse(callback_url)
    path = parsed.path
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


def perform_login(client, sub: str, *, name_prefix: str = "") -> bool:
    """Run the full login flow for a given subject. Returns True on success.

    Each hop is logged under a stable Locust `name=` so that the per-hop
    latency is visible in the stats table even when query params differ.
    """
    p = name_prefix

    # 1. /login/ → 302 to mock /authorize
    r = client.get(
        "/login/",
        allow_redirects=False,
        name=f"{p}01 /login",
    )
    if r.status_code != 302:
        return False
    authorize_url = r.headers.get("Location")
    if not authorize_url:
        return False

    authorize_url = inject_login_hint(authorize_url, sub)

    # 2. mock /authorize → 302 back to /cilogon/callback/?code=…&state=…
    r = client.get(
        authorize_url,
        allow_redirects=False,
        name=f"{p}02 IdP /authorize",
    )
    if r.status_code != 302:
        return False
    callback_url = r.headers.get("Location")
    if not callback_url:
        return False

    # 3. /cilogon/callback/ — the expensive hop
    r = client.get(
        callback_path_with_query(callback_url),
        allow_redirects=False,
        name=f"{p}03 /cilogon/callback",
    )
    if r.status_code not in (302, 200):
        return False

    return True


def perform_logout(client, *, name_prefix: str = "") -> bool:
    """POST /logout/ using the csrftoken cookie. Returns True on success."""
    p = name_prefix
    csrf = client.cookies.get("csrftoken")
    if not csrf:
        # Touch a page that emits the cookie. /my-profile/ requires login;
        # if we hit it after a successful login, Django sets csrftoken.
        client.get("/my-profile/", allow_redirects=False, name=f"{p}04a /my-profile")
        csrf = client.cookies.get("csrftoken") or ""

    headers = {
        "X-CSRFToken": csrf,
        "Referer": client.base_url,
    }
    r = client.post(
        "/logout/",
        headers=headers,
        allow_redirects=False,
        name=f"{p}05 /logout",
    )
    return r.status_code in (302, 200)
