# Prompt: Update WordPress Authentication Plugin to Use Profiles Identity Broker

## Context

The Knowledge Commons Profiles application has been updated to act as an identity
broker. Previously, WordPress received a CILogon authorization code from Profiles
and exchanged it directly with CILogon for tokens using its own client credentials.
Now, Profiles exchanges the code itself and passes pre-decoded, encrypted userinfo
to WordPress.

## Current WordPress Authentication Flow (to be replaced)

1. User clicks Login on WordPress
2. WordPress encodes its callback URL in a base64 state parameter:
   `{"callback_next": "https://hcommons.org/wp-json/some-endpoint"}`
3. WordPress redirects to `https://profile.hcommons.org/cilogon/login/?state=<b64>`
4. After CILogon authentication, Profiles forwards the authorization code to WordPress
5. WordPress exchanges the code with CILogon using its own client_id/client_secret
6. WordPress creates a local user session

## New Flow (to implement)

1. User clicks Login on WordPress
2. WordPress redirects to:
   `https://profile.hcommons.org/login/?return_to=https://hcommons.org/broker-callback/`
3. Profiles authenticates the user (or skips if already authenticated)
4. Profiles redirects to:
   `https://hcommons.org/broker-callback/?broker_token=<encrypted_payload>`
5. WordPress decrypts the payload and verifies the nonce (see below)
6. WordPress creates/matches a local user and logs them in

## What to Implement

### 1. New endpoint: `/broker-callback/`

Register a new REST API route or rewrite rule that handles the broker callback.

### 2. Decrypt the broker_token

The `broker_token` GET parameter is AES-256-CBC encrypted using a shared secret.

**Decryption steps (PHP)**:
```php
function decrypt_broker_token(string $encrypted_param, string $shared_secret): ?array {
    // Derive 32-byte key from shared secret
    $key = hash('sha256', $shared_secret, true);

    // Base64 URL-safe decode
    $data = base64_decode(strtr($encrypted_param, '-_', '+/'));

    // First 16 bytes are the IV
    $iv = substr($data, 0, 16);
    $encrypted = substr($data, 16);

    // Decrypt with AES-256-CBC
    $decrypted = openssl_decrypt($encrypted, 'aes-256-cbc', $key, OPENSSL_RAW_DATA, $iv);

    if ($decrypted === false) {
        return null;
    }

    return json_decode($decrypted, true);
}
```

The shared secret is the same `STATIC_API_BEARER` value used for existing API
authentication between WordPress and Profiles.

### 3. Validate the payload

The decrypted payload has this structure:
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
    "exp": 1234567950
}
```

Validate:
- `exp` has not passed (`exp > time()`)
- `kc_username` is present and non-empty

### 4. Verify the nonce (back-channel)

Make a server-to-server POST to Profiles to consume the one-time nonce:

```php
$response = wp_remote_post('https://profile.hcommons.org/broker/verify-nonce/', [
    'headers' => [
        'Authorization' => 'Bearer ' . STATIC_API_BEARER,
        'Content-Type'  => 'application/json',
    ],
    'body' => json_encode(['nonce' => $payload['nonce']]),
]);

$body = json_decode(wp_remote_retrieve_body($response), true);

if (wp_remote_retrieve_response_code($response) !== 200 || !$body['valid']) {
    // Nonce invalid or already used — reject login
    wp_die('Authentication failed');
}
```

### 5. Create or match the local WordPress user

Use `kc_username` from the payload to find or create a WordPress user:

```php
$user = get_user_by('login', $payload['kc_username']);

if (!$user) {
    $user_id = wp_insert_user([
        'user_login' => $payload['kc_username'],
        'user_email' => $payload['userinfo']['email'],
        'display_name' => $payload['userinfo']['name'],
        'user_pass' => wp_generate_password(32),
    ]);
    $user = get_user_by('ID', $user_id);
}

// Log the user in
wp_set_current_user($user->ID);
wp_set_auth_cookie($user->ID);

// Redirect to home or original page
wp_redirect(home_url());
exit;
```

### 6. Update the Login button

Change the login redirect from the old state-encoded URL to:
```php
$return_to = urlencode(home_url('/broker-callback/'));
$login_url = "https://profile.hcommons.org/login/?return_to={$return_to}";
wp_redirect($login_url);
```

### 7. What to Remove

- Remove any CILogon client_id / client_secret configuration
- Remove the old OAuth callback that exchanged authorization codes with CILogon
- Remove any CILogon token refresh logic
- Keep the existing logout webhook endpoint (unchanged)
- Keep the existing email sync endpoint at `/wp-json/idms/update-email` (unchanged)

## Security Notes

- The `STATIC_API_BEARER` shared secret must match between WordPress and Profiles
- The nonce is single-use — verify it exactly once, then it is consumed
- The payload expires after 60 seconds — reject if `exp < time()`
- All communication must be over HTTPS
- The broker_token in the URL is encrypted, but avoid logging it
