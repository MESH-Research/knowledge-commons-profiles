# CILogon Features Technical Guide 🔐

> **Note**: This documentation refers to knowledge-commons-profiles version 2.30.0

This document provides a technical overview of the CILogon authentication and authorization features implemented in the Knowledge Commons Profiles repository. CILogon enables federated identity management through OAuth 2.0/OpenID Connect protocols.

## Overview

The CILogon integration provides secure authentication for users through their institutional identities, allowing them to log in using credentials from universities, research institutions, and other federated identity providers. The system handles user registration, profile association, token management, and secure logout across multiple applications.

## Core Components

### 1. Main Application Structure (`knowledge_commons_profiles/cilogon/`)

The CILogon functionality is organized into several key modules:

- **`views.py`** - Main view handlers for authentication flows
- **`oauth.py`** - OAuth client configuration and token management utilities  
- **`models.py`** - Database models for user associations and token storage
- **`middleware.py`** - Token refresh and garbage collection middleware
- **`urls.py`** - URL routing configuration
- **`admin.py`** - Django admin interface configuration

## Authentication Flow 

### 1. Login Process (`views.cilogon_login`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

The login process begins when a user accesses the `/cilogon/login/` endpoint:

1. **State Generation**: Creates a secure state parameter using `pack_state()` to prevent CSRF attacks
2. **Authorization Redirect**: Redirects user to CILogon's authorization server with proper scopes
3. **Session Management**: Stores necessary session variables for callback handling

**Key Functions**:
- `pack_state(next_url)` - Base64 encodes the next URL for state parameter
- OAuth client configured in `oauth.py` with institutional scopes

### 2. OAuth Callback (`views.callback`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

Handles the OAuth callback from CILogon after user authentication:

1. **Token Exchange**: Exchanges authorization code for access/refresh tokens
2. **User Info Retrieval**: Fetches user information from CILogon's userinfo endpoint
3. **Session Storage**: Stores tokens and user info securely in session
4. **User Resolution**: Determines if user exists or needs registration/association

**Key Functions**:
- `get_secure_userinfo(request)` - Validates and retrieves user information
- `store_session_variables(request, token, userinfo)` - Securely stores session data
- `find_user_and_login(request, sub_association)` - Logs in existing users

### 3. User Registration (`views.register`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

Handles new user registration when no existing profile is found:

1. **Validation**: Validates CILogon `sub` (subject identifier) is present
2. **Profile Creation**: Creates new `Profile` object with user details
3. **User Creation**: Creates corresponding Django `User` object
4. **Association**: Links CILogon identity to profile via `SubAssociation`
5. **Auto-Login**: Automatically logs in the newly registered user

**Key Models**:
- `SubAssociation` - Links CILogon `sub` to user profiles
- `Profile` - User profile information
- `User` - Django authentication user

## Data Models 

### SubAssociation Model

**Location**: `knowledge_commons_profiles/cilogon/models.py`

```python
class SubAssociation(models.Model):
    sub = models.CharField(max_length=255, unique=True)  # CILogon subject ID
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
```

Links CILogon subject identifiers to user profiles, enabling persistent authentication across sessions.

### TokenUserAgentAssociations Model

**Location**: `knowledge_commons_profiles/cilogon/models.py`

```python
class TokenUserAgentAssociations(models.Model):
    user_agent = models.CharField(max_length=255)
    access_token = models.TextField()
    refresh_token = models.TextField()
    app = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
```

Manages OAuth tokens per user agent and application, enabling single-logout functionality across multiple services.

### EmailVerification Model

**Location**: `knowledge_commons_profiles/cilogon/models.py`

Handles email verification during the association process when users need to confirm their identity.

## Token Management 

### Automatic Token Refresh

**Location**: `knowledge_commons_profiles/cilogon/middleware.py`

The `AutoRefreshTokenMiddleware` automatically refreshes OAuth tokens before they expire:

1. **Expiration Check**: Monitors token expiration times
2. **Refresh Logic**: Uses refresh tokens to obtain new access tokens
3. **Session Update**: Updates session with new token information
4. **Error Handling**: Manages refresh failures and token revocation

**Key Functions**:
- `token_expired(token, user)` - Checks if token needs refresh
- `refresh_user_token()` - Performs token refresh operation

### Token Garbage Collection

**Location**: `knowledge_commons_profiles/cilogon/middleware.py`

The `GarbageCollectionMiddleware` cleans up expired tokens:

1. **Periodic Cleanup**: Runs at configurable intervals
2. **Token Revocation**: Properly revokes tokens with CILogon
3. **Database Cleanup**: Removes expired token associations
4. **Resource Management**: Prevents token table growth

## Security Features 

### Secure Parameter Encoding

**Location**: `knowledge_commons_profiles/cilogon/oauth.py`

The `SecureParamEncoder` class provides encryption for sensitive URL parameters:

- **AES Encryption**: Uses AES-256-CBC for parameter encryption
- **Key Derivation**: Derives encryption keys from shared secrets
- **URL Safety**: Base64 encoding for URL transmission

### JWT Token Validation

**Location**: `knowledge_commons_profiles/cilogon/oauth.py`

Implements proper JWT validation for CILogon tokens:

- **JWKS Fetching**: Retrieves and caches CILogon's public keys
- **Signature Verification**: Validates token signatures
- **Claims Validation**: Verifies token claims and expiration

### ORCID Integration Fix

**Location**: `knowledge_commons_profiles/cilogon/oauth.py`

The `ORCIDHandledToken` class fixes ORCID-specific token validation issues where the `amr` claim format differs from standard expectations.

## User Association Flow 

### Profile Association (`views.association`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

Handles linking existing profiles to CILogon identities:

1. **Identity Verification**: Confirms user's institutional identity
2. **Profile Matching**: Matches email addresses to existing profiles
3. **Confirmation Process**: May require email verification
4. **Association Creation**: Creates `SubAssociation` link

### Email Verification (`views.activate`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

Handles email-based verification for profile associations:

1. **Token Validation**: Validates verification tokens from email links
2. **Association Completion**: Completes the profile association process
3. **Auto-Login**: Logs user in after successful verification

## Logout and Session Management 

### Application Logout (`views.app_logout`)

**Location**: `knowledge_commons_profiles/cilogon/views.py`

Implements comprehensive logout functionality:

1. **Multi-App Logout**: Logs user out of all associated applications
2. **Token Revocation**: Revokes OAuth tokens with CILogon
3. **Session Cleanup**: Clears all session data
4. **Database Cleanup**: Removes token associations

**Key Features**:
- **Single Logout**: Logs out of all apps sharing the same user agent
- **Token Revocation**: Properly revokes tokens to prevent reuse
- **Configurable Behavior**: Supports different redirect behaviors

## URL Configuration 

**Location**: `knowledge_commons_profiles/cilogon/urls.py`

The CILogon app defines the following URL patterns:

- `/cilogon/login/` - Initiates OAuth login flow
- `/cilogon/logout/` - Handles application logout
- `/cilogon/callback/` - OAuth callback endpoint (configurable)
- `/cilogon/associate/` - Profile association flow
- `/cilogon/register/` - New user registration
- `/cilogon/confirm/` - Email confirmation
- `/cilogon/activate/<int:verification_id>/<str:secret_key>/` - Email verification

## Configuration Settings 

The CILogon integration requires several Django settings:

- `CILOGON_CLIENT_ID` - OAuth client identifier
- `CILOGON_CLIENT_SECRET` - OAuth client secret
- `CILOGON_DISCOVERY_URL` - OpenID Connect discovery endpoint
- `CILOGON_SCOPE` - OAuth scopes (typically includes openid, email, profile)
- `OIDC_CALLBACK` - Callback URL path
- `CILOGON_TOKEN_CLEAROUT_DAYS` - Token cleanup interval

## Error Handling 

The system includes comprehensive error handling:

- **OAuth Errors**: Handles authorization failures and token errors
- **Network Errors**: Manages connectivity issues with CILogon
- **Database Errors**: Handles database connectivity and integrity issues
- **Validation Errors**: Manages invalid user data and token validation failures

**Error Templates**:
- `registration_error.html` - User-friendly registration error page
- Standard Django error handling for other scenarios

## Integration Points 

### External API Integration

**Location**: `knowledge_commons_profiles/cilogon/oauth.py`

The `send_association_message()` function integrates with external APIs to notify other services of user associations.

### Profile System Integration

The CILogon system integrates closely with the profile management system:

- **Profile Creation**: Automatically creates profiles for new users
- **Profile Association**: Links existing profiles to CILogon identities
- **User Management**: Integrates with Django's user authentication system

## Development and Testing 

### Management Commands

**Location**: `knowledge_commons_profiles/cilogon/management/`

The app includes Django management commands for administrative tasks and testing.

### Admin Interface

**Location**: `knowledge_commons_profiles/cilogon/admin.py`

Provides Django admin interface for managing:
- SubAssociations
- TokenUserAgentAssociations  
- EmailVerifications

## Best Practices 

1. **Token Security**: Always use HTTPS in production for token transmission
2. **Session Management**: Implement proper session timeout and cleanup
3. **Error Logging**: Monitor authentication failures and token refresh issues
4. **Database Maintenance**: Regular cleanup of expired tokens and associations
5. **Security Updates**: Keep OAuth libraries and dependencies updated

## Troubleshooting 

Common issues and solutions:

- **Token Refresh Failures**: Check network connectivity and client credentials
- **Association Errors**: Verify email addresses and institutional affiliations
- **Login Loops**: Clear browser sessions and check callback URL configuration
- **Database Locks**: Monitor token refresh middleware for deadlocks

---

This technical guide provides the foundation for understanding and maintaining the CILogon authentication system. For specific implementation details, refer to the individual source files mentioned throughout this document.
