# Universal Logout Implementation Guide

## Overview

Knowledge Commons Profiles acts as a **central logout hub**. When a user logs out of any connected application, that application notifies Profiles, which then:
1. Revokes OAuth tokens at CILogon
2. Clears user sessions locally
3. Relays the logout signal to all other connected applications

**Two roles for external apps:**
1. **Sender** - Send logout signals TO Profiles when a user logs out of your app
2. **Receiver** - Receive logout signals FROM Profiles when a user logged out elsewhere

Most apps need to implement **both** roles.

---

## Part 1: Implementing a Sender (Notify Profiles When User Logs Out)

When a user logs out of your application, you must notify the Profiles API so it can propagate the logout to all connected systems.

### 1.1 Endpoint Details

| Property | Value |
|----------|-------|
| **URL** | `https://profile.hcommons.org/api/v1/actions/logout/` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **Authentication** | `Authorization: Bearer {PROFILES_API_BEARER_TOKEN}` |

### 1.2 Request Body

```json
{
    "user_name": "john_doe",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_name` | string | Yes | The username of the user logging out (cannot be empty) |
| `user_agent` | string | Yes | The browser user-agent string (cannot be empty) |

### 1.3 Django Implementation

```python
# logout_sender.py
import requests
from django.conf import settings


def send_logout_to_profiles(user_name: str, user_agent: str) -> bool:
    """
    Notify Profiles API that a user has logged out.

    Args:
        user_name: The username of the user logging out
        user_agent: The browser user-agent string

    Returns:
        True if successful, False otherwise
    """
    endpoint = f"{settings.PROFILES_API_URL}api/v1/actions/logout/"

    headers = {
        "Authorization": f"Bearer {settings.PROFILES_API_BEARER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = {
        "user_name": user_name,
        "user_agent": user_agent,
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=15,
        )

        if 200 <= response.status_code < 300:
            return True
        else:
            print(f"Logout API returned HTTP {response.status_code}: {response.text[:400]}")
            return False

    except requests.RequestException as e:
        print(f"Error sending logout to Profiles API: {e}")
        return False
```

**Usage in your logout view:**

```python
# views.py
from django.contrib.auth import logout
from django.shortcuts import redirect
from .logout_sender import send_logout_to_profiles


def user_logout(request):
    # Capture user info BEFORE logging out locally
    user_name = request.user.username
    user_agent = request.headers.get("User-Agent", "")

    # 1. Notify Profiles API (this triggers universal logout)
    send_logout_to_profiles(user_name, user_agent)

    # 2. Log out locally
    logout(request)

    # 3. Redirect
    return redirect("/")
```

### 1.4 Flask Implementation

```python
# logout_sender.py
import os
import requests

PROFILES_API_URL = os.environ.get("PROFILES_API_URL", "https://profile.hcommons.org/")
PROFILES_API_BEARER_TOKEN = os.environ.get("PROFILES_API_BEARER_TOKEN")


def send_logout_to_profiles(user_name: str, user_agent: str) -> bool:
    """
    Notify Profiles API that a user has logged out.

    Args:
        user_name: The username of the user logging out
        user_agent: The browser user-agent string

    Returns:
        True if successful, False otherwise
    """
    endpoint = f"{PROFILES_API_URL}api/v1/actions/logout/"

    headers = {
        "Authorization": f"Bearer {PROFILES_API_BEARER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = {
        "user_name": user_name,
        "user_agent": user_agent,
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=15,
        )

        if 200 <= response.status_code < 300:
            return True
        else:
            print(f"Logout API returned HTTP {response.status_code}: {response.text[:400]}")
            return False

    except requests.RequestException as e:
        print(f"Error sending logout to Profiles API: {e}")
        return False
```

**Usage in your Flask logout route:**

```python
# app.py
from flask import Flask, redirect, request, session
from flask_login import logout_user, current_user
from logout_sender import send_logout_to_profiles

app = Flask(__name__)


@app.route("/logout")
def user_logout():
    # Capture user info BEFORE logging out locally
    user_name = current_user.username
    user_agent = request.headers.get("User-Agent", "")

    # 1. Notify Profiles API (this triggers universal logout)
    send_logout_to_profiles(user_name, user_agent)

    # 2. Log out locally
    logout_user()
    session.clear()

    # 3. Redirect
    return redirect("/")
```

### 1.5 Configuration

**Django (settings.py):**
```python
# The base URL of the Profiles application
PROFILES_API_URL = "https://profile.hcommons.org/"

# The shared Bearer token (get this from your Profiles administrator)
PROFILES_API_BEARER_TOKEN = os.environ.get("PROFILES_API_BEARER_TOKEN")
```

**Flask (.env):**
```bash
PROFILES_API_URL=https://profile.hcommons.org/
PROFILES_API_BEARER_TOKEN=your-shared-secret-token
```

### 1.6 Success Response (HTTP 200)

```json
{
    "message": "Action successfully triggered.",
    "data": {
        "user": {
            "user": "john_doe",
            "url": "/profiles/john_doe/"
        },
        "user_agent": "Mozilla/5.0 ...",
        "app": ["Profiles", "Works", "WordPress"]
    }
}
```

### 1.7 Error Responses

**HTTP 400 - Validation Error:**
```json
{
    "error": "Validation failed",
    "details": {
        "user_name": ["Username cannot be empty"],
        "user_agent": ["User agent cannot be empty"]
    }
}
```

**HTTP 401 - Unauthorized:**
Missing or invalid Bearer token.

**HTTP 500 - Server Error:**
```json
{
    "error": "An unexpected error occurred"
}
```

---

## Part 2: Implementing a Receiver (Receive Logout Signals from Profiles)

When a user logs out from another application (or directly from Profiles), Profiles will call your logout endpoint to terminate that user's session in your app.

### 2.1 Endpoint Requirements

You must create an endpoint that:
- Accepts `GET` requests
- Is secured by a shared Bearer token
- Reads the `username` from query parameters
- Logs out the specified user (clears their sessions)

### 2.2 Request Format You Will Receive

```
GET https://your-app.example.org/api/logout/?username=john_doe
Headers:
    Authorization: Bearer {SHARED_BEARER_TOKEN}
    Content-Type: application/json
```

| Component | Description |
|-----------|-------------|
| Method | `GET` |
| Query Param | `username` - The user to log out |
| Auth Header | `Authorization: Bearer {token}` |

### 2.3 Django REST Framework Implementation

```python
# authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from django.contrib.auth.models import AnonymousUser
from django.conf import settings


class StaticBearerAuthentication(BaseAuthentication):
    """Validates the static Bearer token."""

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()

        if len(parts) != 2 or parts[0] != "Bearer":
            return None

        token = parts[1]
        if token != settings.STATIC_API_BEARER:
            return None

        return (AnonymousUser(), token)


class HasStaticBearerToken(BasePermission):
    """Requires valid Bearer token."""

    def has_permission(self, request, view):
        return request.auth == settings.STATIC_API_BEARER
```

```python
# views.py
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model

from .authentication import StaticBearerAuthentication, HasStaticBearerToken

User = get_user_model()


class LogoutReceiverView(APIView):
    """
    Receives logout signals from Knowledge Commons Profiles.

    GET /api/logout/?username=<username>
    Authorization: Bearer <token>
    """
    authentication_classes = [StaticBearerAuthentication]
    permission_classes = [HasStaticBearerToken]

    def get(self, request):
        username = request.query_params.get("username")

        if not username:
            return Response(
                {"error": "username parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Clear all sessions for this user
        try:
            user = User.objects.get(username=username)
            self._clear_user_sessions(user)
        except User.DoesNotExist:
            pass  # User doesn't exist here - that's OK

        return Response(
            {"status": "success", "message": f"User {username} logged out"},
            status=status.HTTP_200_OK
        )

    def _clear_user_sessions(self, user):
        """Delete all Django sessions for this user."""
        for session in Session.objects.all():
            try:
                decoded = session.get_decoded()
                if decoded.get("_auth_user_id") == str(user.pk):
                    session.delete()
            except Exception:
                continue
```

```python
# urls.py
from django.urls import path
from .views import LogoutReceiverView

urlpatterns = [
    path("api/logout/", LogoutReceiverView.as_view(), name="logout-receiver"),
]
```

**Configuration (settings.py):**
```python
# The shared Bearer token (must match the one configured in Profiles)
STATIC_API_BEARER = os.environ.get("STATIC_API_BEARER")
```

### 2.4 Flask Implementation

```python
# app.py
from flask import Flask, request, jsonify
from functools import wraps
import os

app = Flask(__name__)
STATIC_API_BEARER = os.environ.get("STATIC_API_BEARER")


def require_bearer_token(f):
    """Decorator to require valid Bearer token authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = auth_header.split(" ", 1)[1]
        if token != STATIC_API_BEARER:
            return jsonify({"error": "Invalid Bearer token"}), 401

        return f(*args, **kwargs)
    return decorated


@app.route("/api/logout/", methods=["GET"])
@require_bearer_token
def logout_receiver():
    """
    Receives logout signals from Knowledge Commons Profiles.

    GET /api/logout/?username=<username>
    Authorization: Bearer <token>
    """
    username = request.args.get("username")

    if not username:
        return jsonify({"error": "username parameter required"}), 400

    # Clear all sessions for this user
    clear_user_sessions(username)

    return jsonify({
        "status": "success",
        "message": f"User {username} logged out"
    })


def clear_user_sessions(username: str):
    """
    Clear all sessions for the specified user.
    Implement based on your session storage.
    """
    # Example with Flask-Session using Redis:
    # from flask import session
    # from your_app.models import User
    #
    # user = User.query.filter_by(username=username).first()
    # if user:
    #     # Delete sessions from your session store
    #     redis_client.delete(f"session:{user.id}")

    # Example with Flask-Login:
    # Mark user's sessions as invalid in your database
    pass
```

**Flask with SQLAlchemy session tracking:**

```python
# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class UserSession(db.Model):
    """Track user sessions for logout functionality."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# In your logout_receiver endpoint:
def clear_user_sessions(username: str):
    """Clear all sessions for the specified user."""
    from your_app.models import User, UserSession, db

    user = User.query.filter_by(username=username).first()
    if user:
        UserSession.query.filter_by(user_id=user.id).delete()
        db.session.commit()
```

**Configuration (.env):**
```bash
STATIC_API_BEARER=your-shared-secret-token
```

### 2.5 Response Requirements

Profiles considers any HTTP status < 400 as success.

**Success (HTTP 200):**
```json
{
    "status": "success",
    "message": "User john_doe logged out"
}
```

**Important:** Return HTTP 200 even if the user doesn't exist in your system.

### 2.6 Register Your Endpoint with Profiles

Contact your Profiles administrator to add your logout endpoint to the `LOGOUT_ENDPOINTS` list in Profiles settings:

```python
# In Profiles settings.py
LOGOUT_ENDPOINTS = [
    "https://your-app.example.org/api/logout/",
    # ... other endpoints
]
```

---

## Part 3: Security Considerations

### 3.1 Bearer Token

- **Keep it secret** - Store in environment variables, never in code
- **Same token everywhere** - All connected apps must use the same token
- **Use HTTPS** - Always use TLS to protect the token in transit
- **Generate securely:**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

### 3.2 Environment Setup

**Django:**
```python
# settings.py
import os

PROFILES_API_URL = os.environ.get("PROFILES_API_URL", "https://profile.hcommons.org/")
PROFILES_API_BEARER_TOKEN = os.environ.get("PROFILES_API_BEARER_TOKEN")
STATIC_API_BEARER = os.environ.get("STATIC_API_BEARER")  # For receiving
```

**Flask:**
```python
# config.py
import os

PROFILES_API_URL = os.environ.get("PROFILES_API_URL", "https://profile.hcommons.org/")
PROFILES_API_BEARER_TOKEN = os.environ.get("PROFILES_API_BEARER_TOKEN")
STATIC_API_BEARER = os.environ.get("STATIC_API_BEARER")
```

**.env file:**
```bash
PROFILES_API_URL=https://profile.hcommons.org/
PROFILES_API_BEARER_TOKEN=your-secure-token-here
STATIC_API_BEARER=your-secure-token-here
```

---

## Part 4: Complete Flow Diagram

```
User logs out of WordPress
         │
         ▼
┌─────────────────────┐
│ WordPress sends     │  POST https://profile.hcommons.org/api/v1/actions/logout/
│ logout TO Profiles  │  Body: {user_name, user_agent}
└─────────┬───────────┘  Auth: Bearer <token>
          │
          ▼
┌─────────────────────┐
│ Profiles receives   │
│ logout request      │
│                     │
│ 1. Revokes tokens   │
│    at CILogon       │
│ 2. Clears local     │
│    sessions         │
│ 3. Relays logout    │
│    to other apps    │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌─────────┐ ┌─────────┐
│ KC Works│ │Other App│  GET /api/logout/?username=X
│ receives│ │ receives│  Auth: Bearer <token>
│ logout  │ │ logout  │
└─────────┘ └─────────┘
```

---

## Part 5: Testing

### Test Sending to Profiles

```bash
curl -X POST "https://profile.hcommons.org/api/v1/actions/logout/" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "user_agent": "TestAgent/1.0"}'
```

### Test Your Receiver Endpoint

```bash
curl -X GET "https://your-app.example.org/api/logout/?username=testuser" \
  -H "Authorization: Bearer your-token-here"
```

### Python Test Script

```python
import requests

# Test sending logout to Profiles
def test_send_logout():
    response = requests.post(
        "https://profile.hcommons.org/api/v1/actions/logout/",
        headers={
            "Authorization": "Bearer your-token-here",
            "Content-Type": "application/json",
        },
        json={
            "user_name": "testuser",
            "user_agent": "TestAgent/1.0",
        },
        timeout=15,
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")


# Test receiving logout signal
def test_receive_logout():
    response = requests.get(
        "https://your-app.example.org/api/logout/",
        headers={"Authorization": "Bearer your-token-here"},
        params={"username": "testuser"},
        timeout=15,
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
```

---

## Summary Checklist

### Sender (notify Profiles when user logs out of your app):
- [ ] Call `POST https://profile.hcommons.org/api/v1/actions/logout/`
- [ ] Include `Authorization: Bearer {token}` header
- [ ] Send JSON body with `user_name` and `user_agent`
- [ ] Call this BEFORE clearing local sessions
- [ ] Configure `PROFILES_API_URL` and `PROFILES_API_BEARER_TOKEN`

### Receiver (handle logout signals from Profiles):
- [ ] Create endpoint at `/api/logout/` (or similar)
- [ ] Accept `GET` requests with `username` query parameter
- [ ] Validate `Authorization: Bearer {token}` header
- [ ] Clear all sessions for the specified user
- [ ] Return HTTP 200 (even if user doesn't exist)
- [ ] Configure `STATIC_API_BEARER`
- [ ] Register your endpoint URL with Profiles administrator

---

## Source Files Reference

- Profiles logout endpoint: `knowledge_commons_profiles/rest_api/views.py` (LogoutView)
- Logout serializer: `knowledge_commons_profiles/rest_api/serializers/serializers.py` (LogoutSerializer)
- Bearer authentication: `knowledge_commons_profiles/rest_api/authentication.py` (StaticBearerAuthentication)
- Logout relay to external apps: `knowledge_commons_profiles/rest_api/utils.py` (logout_all_endpoints_sync)
- Main logout logic: `knowledge_commons_profiles/cilogon/views.py` (app_logout)
