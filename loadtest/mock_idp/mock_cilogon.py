"""Mock CILogon OIDC provider for load testing.

Exposes the OIDC discovery + JWKS + authorize + token + userinfo endpoints
that the IDMS's Authlib client expects. Auto-approves authorize requests
based on a `login_hint` query parameter (mapped 1:1 to the OIDC `sub`
claim) and immediately 302s back to the redirect URI with a code.

Claim shape mirrors what `knowledge_commons_profiles/cilogon/` actually
parses: sub, eppn, eptid, email, given_name, family_name, idp_name, idp.

Run with multiple workers so the mock isn't itself the bottleneck:
    uvicorn mock_cilogon:app --host 0.0.0.0 --port 8080 --workers 4
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from authlib.jose import JsonWebKey
from authlib.jose import jwt
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

logger = logging.getLogger("mock_cilogon")
logging.basicConfig(level=logging.INFO)

ISSUER = os.environ.get("MOCK_ISSUER", "http://mock-oidc:8080")
ARTIFICIAL_LATENCY_MS = int(os.environ.get("MOCK_LATENCY_MS", "150"))
DEFAULT_AUDIENCE = os.environ.get("MOCK_DEFAULT_AUDIENCE", "loadtest")
ID_TOKEN_TTL_SECONDS = int(os.environ.get("MOCK_ID_TOKEN_TTL", "3600"))
# Persist the RSA keypair so all uvicorn workers share one kid. Without
# this, each worker generates its own pair at import time and Authlib in
# the relying party gets a `Key not found` when JWKS came from worker A
# but the token was signed by worker B.
KEY_FILE = Path(os.environ.get("MOCK_KEY_FILE", "/tmp/mock_idp_key.json"))  # noqa: S108


@contextlib.contextmanager
def _exclusive_file_lock(lock_path: Path):
    """Process-wide exclusive lock so only one uvicorn worker generates the
    keypair; others block here until the file is ready, then read it."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _load_or_create_key() -> tuple[Any, dict[str, Any], str]:
    """Return (private_key, public_jwk_dict, kid).

    All uvicorn workers contend for an exclusive file lock. The winner
    writes the keypair to disk; the rest read it. After this function
    returns, every worker holds the same kid, so JWKS published by one
    worker matches a token signed by any other.
    """
    lock_path = KEY_FILE.parent / (KEY_FILE.name + ".lock")
    with _exclusive_file_lock(lock_path):
        if KEY_FILE.exists():
            try:
                data = json.loads(KEY_FILE.read_text())
                key = JsonWebKey.import_key(data["private"])
                public_jwk = data["public"]
                kid = public_jwk["kid"]
                logger.info(
                    "mock_cilogon: loaded persisted keypair kid=%s", kid
                )
                return key, public_jwk, kid
            except Exception:
                logger.exception(
                    "mock_cilogon: %s exists but is unreadable; regenerating",
                    KEY_FILE,
                )

        key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
        private_jwk = key.as_dict(is_private=True)
        public_jwk = key.as_dict(is_private=False)
        public_jwk.setdefault("use", "sig")
        public_jwk.setdefault("alg", "RS256")
        kid = public_jwk.get("kid") or uuid.uuid4().hex
        public_jwk["kid"] = kid
        private_jwk["kid"] = kid

        tmp = KEY_FILE.with_suffix(KEY_FILE.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"private": private_jwk, "public": public_jwk})
        )
        tmp.replace(KEY_FILE)
        logger.info(
            "mock_cilogon: generated new keypair kid=%s -> %s",
            kid,
            KEY_FILE,
        )
        return key, public_jwk, kid


_KEY, _PUBLIC_JWK, _KID = _load_or_create_key()

app = FastAPI(title="Mock CILogon for IDMS load testing")

# Authorization codes are stateless: the code itself is a base64url-encoded
# JSON payload carrying the data /token needs (sub, nonce, redirect_uri,
# client_id, expiry). This means any uvicorn worker can redeem any code,
# which matters because /authorize and /token rarely land on the same
# worker. Replay protection is intentionally NOT enforced — load testing
# isn't a security boundary, and a shared anti-replay set across workers
# would re-introduce the very state-sharing problem we're avoiding here.
CODE_TTL_SECONDS = 300


def _encode_code(payload: dict[str, Any]) -> str:
    payload = dict(payload)
    payload["exp"] = int(time.time()) + CODE_TTL_SECONDS
    raw = json.dumps(payload, separators=(",", ":")).encode()
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_code(code: str) -> dict[str, Any] | None:
    import base64

    try:
        padded = code + "=" * (-len(code) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, TypeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def _oauth_error(
    error: str, description: str = "", status_code: int = 400
) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if description:
        body["error_description"] = description
    return JSONResponse(body, status_code=status_code)


@app.get("/.well-known/openid-configuration")
def discovery() -> dict[str, Any]:
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "userinfo_endpoint": f"{ISSUER}/userinfo",
        "revocation_endpoint": f"{ISSUER}/revoke",
        "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": [
            "openid",
            "email",
            "profile",
            "org.cilogon.userinfo",
            "offline_access",
        ],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "iat",
            "exp",
            "nonce",
            "email",
            "eppn",
            "eptid",
            "given_name",
            "family_name",
            "idp_name",
            "idp",
        ],
    }


@app.get("/.well-known/jwks.json")
def jwks() -> dict[str, Any]:
    return {"keys": [_PUBLIC_JWK]}


@app.get("/authorize")
def authorize(request: Request):
    qp = dict(request.query_params)
    redirect_uri = qp.get("redirect_uri")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="missing redirect_uri")

    sub = qp.get("login_hint") or f"loadtest_{uuid.uuid4().hex[:8]}"
    code = _encode_code(
        {
            "sub": sub,
            "nonce": qp.get("nonce"),
            "redirect_uri": redirect_uri,
            "client_id": qp.get("client_id"),
        }
    )
    state = qp.get("state", "")
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{sep}code={code}&state={state}",
        status_code=302,
    )


@app.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    refresh_token: str | None = Form(None),
):
    if ARTIFICIAL_LATENCY_MS:
        time.sleep(ARTIFICIAL_LATENCY_MS / 1000.0)

    if grant_type == "refresh_token":
        if not refresh_token:
            return _oauth_error(
                "invalid_grant", "missing refresh_token"
            )
        return _issue_token_response(
            sub=f"refresh_{uuid.uuid4().hex[:8]}",
            audience=client_id or DEFAULT_AUDIENCE,
            nonce=None,
        )

    if grant_type != "authorization_code":
        return _oauth_error("unsupported_grant_type", grant_type or "")

    if not code:
        return _oauth_error("invalid_grant", "missing code")

    info = _decode_code(code)
    if info is None:
        return _oauth_error(
            "invalid_grant", "code is unknown, malformed, or expired"
        )

    return _issue_token_response(
        sub=info["sub"],
        audience=client_id or info.get("client_id") or DEFAULT_AUDIENCE,
        nonce=info.get("nonce"),
    )


@app.get("/userinfo")
def userinfo(request: Request) -> dict[str, Any]:
    sub = request.query_params.get("sub", "loadtest")
    return _build_claims(sub=sub, audience=DEFAULT_AUDIENCE, nonce=None)


@app.post("/revoke")
def revoke() -> JSONResponse:
    return JSONResponse({"revoked": True})


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "issuer": ISSUER,
        "kid": _KID,
    }


def _build_claims(
    *, sub: str, audience: str, nonce: str | None
) -> dict[str, Any]:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": sub,
        "aud": audience,
        "iat": now,
        "exp": now + ID_TOKEN_TTL_SECONDS,
        "eppn": f"{sub}@example.invalid",
        "eptid": f"{sub}!example.invalid!{sub}",
        "email": f"{sub}@example.invalid",
        "given_name": "Load",
        "family_name": "Test",
        "idp_name": "Mock IdP for Load Testing",
        "idp": "https://idp.example.invalid/idp/shibboleth",
    }
    if nonce:
        claims["nonce"] = nonce
    return claims


def _issue_token_response(
    *, sub: str, audience: str, nonce: str | None
) -> JSONResponse:
    claims = _build_claims(sub=sub, audience=audience, nonce=nonce)
    header = {"alg": "RS256", "kid": _KID}
    id_token = jwt.encode(header, claims, _KEY).decode()
    return JSONResponse(
        {
            "access_token": uuid.uuid4().hex,
            "token_type": "Bearer",
            "expires_in": ID_TOKEN_TTL_SECONDS,
            "refresh_token": uuid.uuid4().hex,
            "id_token": id_token,
            "scope": "openid email profile org.cilogon.userinfo offline_access",
        }
    )
