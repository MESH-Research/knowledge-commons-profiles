# Identity Broker Integration Guide for Works

## What Changed

Profiles is now an identity broker. Works no longer exchanges CILogon authorization
codes directly. Instead, it receives pre-decoded userinfo from Profiles via an
encrypted `broker_token`.

## Migration from the Old Flow

The old flow forwarded authorization codes via the `callback_next` state parameter,
and Works then exchanged the code with CILogon using its own client credentials.
This is being replaced. Works no longer needs its own CILogon `client_id` or
`client_secret`.

## New Login Flow

1. Works redirects the user to:
   ```
   https://profile.hcommons.org/login/?return_to=https://works.hcommons.org/broker-callback/&final_redirect=https://works.hcommons.org/original-page/
   ```
   The `final_redirect` parameter is optional. When provided, it is included in the
   encrypted `broker_token` payload so Works can redirect the user back to the exact
   page they came from after completing login.
2. Profiles authenticates the user (or recognizes an existing session) and redirects
   back to Works with:
   ```
   https://works.hcommons.org/broker-callback/?broker_token=<encrypted>
   ```
3. Works decrypts the token and verifies the nonce.

## Silent Login Check

Works can check if a user already has an active Profiles session without showing
any login UI. This enables transparent SSO — Works can silently detect existing
sessions on page load or periodically.

### Endpoint

```
GET https://profile.hcommons.org/broker/silent-login/?return_to=<callback_url>&final_redirect=<original_page>
```

The `final_redirect` parameter is optional and works the same way as in the login flow.

### Behavior

- **User is authenticated**: redirects to `return_to` with `broker_token=<encrypted>`
  (same format as the normal login flow — decrypt and verify the nonce the same way).
- **User is not authenticated**: redirects to `return_to?no_session=1`. If `final_redirect`
  was provided, it is appended as `&final_redirect=<url-encoded>` so the consuming app
  can redirect the user to the original page after handling the no-session case.
- **Missing or invalid `return_to`**: returns HTTP 400. The `return_to` domain must be
  in the allowed domain list (same allowlist as the login flow).

### Recommended usage

Call this endpoint from an iframe or background request (e.g., every ~30 minutes) to
detect existing sessions. The `broker_token` returned uses the same payload structure
and nonce verification as the normal login flow.

## What Works Needs to Implement

### 1. A `/broker-callback/` endpoint

Register a new route that handles the redirect from Profiles and reads the
`broker_token` query parameter.

### 2. Decryption logic using `SecureParamEncoder`

The `broker_token` is AES-256-CBC encrypted using a shared secret
(`STATIC_API_BEARER`). Here is a Python reference implementation:

```python
import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


class SecureParamEncoder:
    """Encrypt and decrypt payloads using AES-256-CBC with a shared secret."""

    def __init__(self, secret: str):
        self.key = hashlib.sha256(secret.encode()).digest()

    def decrypt(self, encrypted_param: str) -> dict:
        data = base64.urlsafe_b64decode(encrypted_param)
        iv = data[:16]
        encrypted = data[16:]
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        return json.loads(plaintext)
```

Usage:

```python
encoder = SecureParamEncoder(settings.STATIC_API_BEARER)
payload = encoder.decrypt(request.GET["broker_token"])
```

### 3. Nonce verification

After decrypting the payload, verify the one-time nonce with a back-channel POST
to Profiles:

```
POST https://profile.hcommons.org/broker/verify-nonce/
Authorization: Bearer <STATIC_API_BEARER>
Content-Type: application/json

{"nonce": "<nonce>"}
```

A `200` response with `{"valid": true}` means the nonce is good. Any other response
means the nonce is invalid or already consumed — reject the login.

### 4. Local user lookup/creation

Use the `kc_username` field from the payload to find or create a local user.

## Payload Structure

```json
{
    "userinfo": {
        "sub": "http://cilogon.org/serverA/users/12345",
        "email": "user@example.com",
        "name": "Jane Doe",
        "idp_name": "University of Example"
    },
    "kc_username": "jdoe",
    "nonce": "abc123...",
    "iat": 1234567890,
    "exp": 1234567950,
    "final_redirect": "https://works.hcommons.org/original-page/"
}
```

- `userinfo` contains the identity attributes from CILogon.
- `kc_username` is the canonical username in the Knowledge Commons ecosystem.
- `nonce` is a single-use token that must be verified via the back-channel endpoint.
- `iat` is the issued-at timestamp (Unix epoch).
- `exp` is the expiration timestamp (Unix epoch, typically 60 seconds after `iat`).
  Reject the payload if `exp` has passed.
- `final_redirect` is the URL where the user originally wanted to go. If non-empty,
  redirect the user there after completing login. If empty, use your default post-login
  destination.

## Logout

No changes are required. The existing `LOGOUT_ENDPOINTS` mechanism continues to
work as before.

## What to Remove

- Works' CILogon OAuth client registration (`client_id` / `client_secret`)
- The token exchange logic that sent authorization codes to CILogon
- Any CILogon-specific middleware or token refresh logic
