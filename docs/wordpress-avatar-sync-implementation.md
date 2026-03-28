# WordPress Avatar Sync: Receiver Implementation Guide

**Related issues:**
- Profiles side: [MESH-Research/knowledge-commons-profiles#392](https://github.com/MESH-Research/knowledge-commons-profiles/issues/392)
- WordPress side: [MESH-Research/knowledge-commons-wordpress#60](https://github.com/MESH-Research/knowledge-commons-wordpress/issues/60)

## Overview

When a user uploads a new profile avatar on Knowledge Commons Profiles, the Profiles app sends a POST request to WordPress with the avatar image URL. WordPress must expose a REST API endpoint to receive this request, download the image, and update the user's BuddyPress avatar so that all WordPress-backed UI surfaces (navigation bar, comments, activity feed, etc.) reflect the new image.

This document describes what the WordPress plugin must implement to complete the integration. The sending side (Profiles) is already implemented.

## What the Profiles App Sends

### Endpoint

The Profiles app sends a POST request to:

```
https://{WORDPRESS_DOMAIN}/wp-json/idms/update-avatar
```

This follows the same namespace and pattern as the existing `update-email` endpoint (`/wp-json/idms/update-email`).

### Request Format

```http
POST /wp-json/idms/update-avatar HTTP/1.1
Host: hcommons.org
Content-Type: application/json
Authorization: Bearer {STATIC_API_BEARER}
x-auth: {STATIC_API_BEARER}

{
    "username": "jsmith",
    "image_url": "https://s3.amazonaws.com/bucket/media/profile_images/abc123.jpg"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | The Commons username of the user whose avatar changed. This matches the WordPress/BuddyPress username. |
| `image_url` | string | The full public URL to the new avatar image. The image is a 150×150 JPEG hosted on S3 (production) or local media storage (development). |

### Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `Authorization` | `Bearer {token}` | Standard Bearer token authentication. The token value is the `STATIC_API_BEARER` environment variable, shared between Profiles and WordPress. |
| `x-auth` | `{token}` | Legacy/secondary auth header. Both headers carry the same token value. The existing `update-email` endpoint validates against `x-auth`, so both are sent for consistency. |
| `Content-Type` | `application/json` | The request body is JSON. |

### Timeout

The Profiles app sets a **10-second timeout** on the request. The WordPress endpoint should complete within this window. If the avatar download or processing will take longer, consider accepting the request immediately (returning 200) and processing asynchronously via `wp_schedule_single_event()` or a background job.

## Authentication and Security

### Bearer Token

The request is authenticated using the **`STATIC_API_BEARER`** token. This is the same shared secret used by the existing `/wp-json/idms/update-email` endpoint.

- **Environment variable name (Profiles side):** `STATIC_API_BEARER`
- **Where to validate (WordPress side):** Check `$_SERVER['HTTP_AUTHORIZATION']` or `$_SERVER['HTTP_X_AUTH']` against the stored token value.
- **On auth failure:** Return HTTP `401 Unauthorized` with a JSON error body.

### Validation Checklist

The WordPress endpoint must:

1. **Verify the Bearer token** matches the shared secret (same validation as `update-email`).
2. **Verify the `username` exists** in WordPress. Return `404` if the user is not found.
3. **Verify the `image_url` is a valid URL** and is from an allowed domain (e.g., the S3 bucket domain or the Profiles media domain). Do not accept arbitrary URLs.
4. **Verify the downloaded image is a valid JPEG** (check magic bytes / MIME type after download). The Profiles app always sends 150×150 JPEG images.
5. **Reject oversized images** — the avatar is always 150×150 at quality 90, so it will be well under 1 MB. Set a reasonable download size limit (e.g., 2 MB).

### Allowed Image Domains

In production, image URLs will be from the S3 bucket configured for the Profiles app. Examples:

- `https://{DJANGO_AWS_S3_CUSTOM_DOMAIN}/media/profile_images/{uuid}.jpg`
- `https://s3.{region}.amazonaws.com/{bucket}/media/profile_images/{uuid}.jpg`

In development/staging, URLs may be from localhost or the local Docker network.

The plugin should maintain a whitelist of allowed image URL domains, configurable via a WordPress option or constant.

## Expected Responses

### Success

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "success": true,
    "avatar_url": "https://hcommons.org/app/uploads/avatars/123/bpfull.jpg",
    "message": "Avatar updated for user jsmith"
}
```

The `avatar_url` field should contain the URL of the avatar as it is now served by WordPress (the resolved BuddyPress avatar URL). This is informational — the Profiles app does not currently use it but it aids debugging.

### Error Responses

| Status | When | Example body |
|--------|------|-------------|
| `400` | Missing or invalid `username` or `image_url` | `{"success": false, "error": "Missing required field: image_url"}` |
| `401` | Invalid or missing Bearer token | `{"success": false, "error": "Unauthorized"}` |
| `404` | Username does not exist in WordPress | `{"success": false, "error": "User not found: jsmith"}` |
| `422` | Image download failed or image is not valid JPEG | `{"success": false, "error": "Failed to download image"}` |
| `500` | Internal server error | `{"success": false, "error": "Internal server error"}` |

## Implementation Steps (WordPress/PHP)

### 1. Register the REST Route

Register the endpoint in the same plugin that handles `update-email` (the IDMS plugin), following the same pattern:

```php
add_action('rest_api_init', function () {
    register_rest_route('idms', '/update-avatar', [
        'methods'  => 'POST',
        'callback' => 'idms_update_avatar',
        'permission_callback' => 'idms_verify_bearer_token',
    ]);
});
```

Use the **same `permission_callback`** as the `update-email` endpoint (`idms_verify_bearer_token` or equivalent) to validate the Bearer token.

### 2. Implement the Callback

```php
function idms_update_avatar(WP_REST_Request $request) {
    $username  = sanitize_user($request->get_param('username'));
    $image_url = esc_url_raw($request->get_param('image_url'));

    if (empty($username) || empty($image_url)) {
        return new WP_REST_Response(
            ['success' => false, 'error' => 'Missing required fields'],
            400
        );
    }

    // Validate image URL domain against whitelist
    if (!idms_is_allowed_image_domain($image_url)) {
        return new WP_REST_Response(
            ['success' => false, 'error' => 'Image URL domain not allowed'],
            400
        );
    }

    // Look up the WordPress user
    $user = get_user_by('login', $username);
    if (!$user) {
        return new WP_REST_Response(
            ['success' => false, 'error' => "User not found: {$username}"],
            404
        );
    }

    // Download the image to a temporary file
    $tmp = download_url($image_url, 10); // 10-second timeout
    if (is_wp_error($tmp)) {
        return new WP_REST_Response(
            ['success' => false, 'error' => 'Failed to download image'],
            422
        );
    }

    // Validate the downloaded file is a JPEG
    $filetype = wp_check_filetype($tmp, ['jpg' => 'image/jpeg']);
    if ($filetype['type'] !== 'image/jpeg') {
        @unlink($tmp);
        return new WP_REST_Response(
            ['success' => false, 'error' => 'Image is not a valid JPEG'],
            422
        );
    }

    // Update the BuddyPress avatar
    // (See section 3 below for BuddyPress-specific avatar handling)
    $result = idms_set_buddypress_avatar($user->ID, $tmp);
    @unlink($tmp); // Clean up temp file

    if (is_wp_error($result)) {
        return new WP_REST_Response(
            ['success' => false, 'error' => $result->get_error_message()],
            500
        );
    }

    return new WP_REST_Response([
        'success'    => true,
        'avatar_url' => $result,
        'message'    => "Avatar updated for user {$username}",
    ], 200);
}
```

### 3. Set the BuddyPress Avatar

BuddyPress stores avatars as files in `wp-content/uploads/avatars/{user_id}/`. The avatar filenames follow the pattern `bpfull.jpg` and `bpthumb.jpg`.

```php
function idms_set_buddypress_avatar($user_id, $tmp_file) {
    if (!function_exists('bp_core_avatar_upload_path')) {
        return new WP_Error('bp_missing', 'BuddyPress is not active');
    }

    $avatar_dir = bp_core_avatar_upload_path() . '/avatars/' . $user_id;

    // Create directory if it doesn't exist
    if (!is_dir($avatar_dir)) {
        wp_mkdir_p($avatar_dir);
    }

    // Delete existing avatars
    $existing = glob($avatar_dir . '/*');
    foreach ($existing as $file) {
        if (is_file($file)) {
            @unlink($file);
        }
    }

    // Copy the downloaded image as both full and thumb
    // The Profiles app already sends a 150x150 image
    $full_path  = $avatar_dir . '/bpfull.jpg';
    $thumb_path = $avatar_dir . '/bpthumb.jpg';

    if (!copy($tmp_file, $full_path) || !copy($tmp_file, $thumb_path)) {
        return new WP_Error('copy_failed', 'Failed to save avatar files');
    }

    // Invalidate any cached avatar URLs
    wp_cache_delete("bp_core_avatar_url_{$user_id}", 'bp');
    bp_core_delete_existing_avatar([
        'item_id' => $user_id,
        'object'  => 'user',
        'no_delete' => true, // We already placed the files
    ]);

    // Return the public URL of the new avatar
    $avatar_url = bp_core_avatar_url() . '/avatars/' . $user_id . '/bpfull.jpg';
    return $avatar_url;
}
```

### 4. Cache Invalidation

After updating the avatar files, ensure stale cached versions are cleared:

- **BuddyPress object cache:** `wp_cache_delete()` for the user's avatar cache keys.
- **WordPress object cache:** If using Redis or Memcached, the cache entries for the user's avatar will need to be invalidated.
- **CDN cache:** If a CDN (e.g., CloudFront) caches avatar URLs, consider appending a cache-busting query parameter (e.g., `?v={timestamp}`) to the avatar URL, or issuing a CDN invalidation.
- **Browser cache:** Avatar URLs served with long `Cache-Control` headers may remain stale in users' browsers. Using versioned URLs (query string with timestamp or hash) helps here.

### 5. Domain Whitelist Helper

```php
function idms_is_allowed_image_domain($url) {
    $allowed_domains = apply_filters('idms_allowed_avatar_domains', [
        // Add your S3 bucket domain and any staging domains
        'knowledge-commons-profiles.s3.amazonaws.com',
        'cdn.hcommons.org',
    ]);

    $host = wp_parse_url($url, PHP_URL_HOST);
    foreach ($allowed_domains as $domain) {
        if ($host === $domain || str_ends_with($host, '.' . $domain)) {
            return true;
        }
    }
    return false;
}
```

## Image Details

The avatar image sent by Profiles has these properties:

| Property | Value |
|----------|-------|
| Format | JPEG |
| Dimensions | 150×150 pixels |
| Quality | 90 (Pillow JPEG quality) |
| Color mode | RGB (alpha channel stripped) |
| EXIF data | Stripped |
| Max file size | ~50 KB typical, always under 1 MB |
| Filename pattern | `profile_images/{uuid4_hex}.jpg` |

## Existing Pattern Reference

The implementation should mirror the existing `update-email` endpoint. In the Profiles codebase, the email sync function is at:

- **`knowledge_commons_profiles/cilogon/oauth.py`** → `sync_email_to_wordpress()`

The avatar sync function follows the same structure:

- **`knowledge_commons_profiles/newprofile/wordpress_sync.py`** → `sync_avatar_to_wordpress()`

Both use `STATIC_API_BEARER` for auth and send JSON payloads via POST.

## Testing

### Manual Testing

1. Set `WORDPRESS_AVATAR_UPDATE_URL` and `STATIC_API_BEARER` in the WordPress environment.
2. Upload a new avatar on the Profiles edit page.
3. Verify the WordPress REST endpoint receives the request (check WordPress debug log).
4. Verify the BuddyPress avatar files are updated in `wp-content/uploads/avatars/{user_id}/`.
5. Verify the avatar displays correctly in the WordPress navigation bar and other UI surfaces.
6. Verify cache invalidation works — the old avatar should not persist.

### Automated Testing (PHPUnit)

- Test that the endpoint returns `401` without a valid Bearer token.
- Test that the endpoint returns `404` for a non-existent username.
- Test that the endpoint returns `400` for missing fields.
- Test that the endpoint returns `200` and updates avatar files for a valid request.
- Test that the domain whitelist rejects URLs from disallowed domains.

## Sequence Diagram

```
User                  Profiles App              S3              WordPress
 |                        |                      |                   |
 |-- Upload avatar ------>|                      |                   |
 |                        |-- Save to S3 ------->|                   |
 |                        |<-- S3 URL -----------|                   |
 |                        |                      |                   |
 |                        |-- POST /wp-json/idms/update-avatar ----->|
 |                        |   {username, image_url}                  |
 |                        |   Authorization: Bearer {token}          |
 |                        |                      |                   |
 |                        |                      |<-- Download image-|
 |                        |                      |-- JPEG data ----->|
 |                        |                      |                   |
 |                        |                      |   Save to         |
 |                        |                      |   avatars/{id}/   |
 |                        |                      |   Invalidate cache|
 |                        |                      |                   |
 |                        |<-- 200 OK {avatar_url} -----------------|
 |<-- Avatar updated -----|                      |                   |
```
