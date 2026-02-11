# Environment Variables Technical Guide

> **Version Note**: This documentation is for knowledge-commons-profiles version 3.15.0

## Overview

This guide documents the environment variables used for application startup and configuration in the Profiles App. Environment variables provide a secure and flexible way to configure the application across different deployment environments (local, development, production) without hardcoding sensitive values.

## Core Application Variables

### DJANGO_SECRET_KEY
- **Purpose**: Django's secret key for cryptographic signing
- **Type**: String
- **Required**: Yes (production/dev), has default for local
- **Security**: Highly sensitive, must be unique per environment
- **Example**: `DJANGO_SECRET_KEY=your-secret-key-here`

### DJANGO_DEBUG
- **Purpose**: Controls Django's debug mode
- **Type**: Boolean
- **Default**: False (production), True (local/development)
- **Usage**: Enables detailed error pages, debug toolbar, and development features
- **Security**: Must be False in production environments
- **Example**: `DJANGO_DEBUG=True`

### DJANGO_READ_DOT_ENV_FILE
- **Purpose**: Whether to read environment variables from a .env file
- **Type**: Boolean
- **Default**: False
- **Usage**: Enable when using a .env file for local development
- **Example**: `DJANGO_READ_DOT_ENV_FILE=True`

### USE_DOCKER
- **Purpose**: Flag to indicate if the application is running in a Docker environment
- **Type**: String ("yes" or "no")
- **Default**: "no"
- **Usage**: Used in local settings to configure internal IPs for Django Debug Toolbar when running in Docker containers
- **Example**: `USE_DOCKER=yes`

### DJANGO_ADMIN_URL
- **Purpose**: Custom URL path for Django admin interface
- **Type**: String
- **Required**: Yes (production/dev)
- **Security**: Use a non-obvious path in production
- **Example**: `DJANGO_ADMIN_URL=secret-admin-path/`

## Database Variables

### DATABASE_URL
- **Purpose**: Primary database connection string for the Profiles App
- **Type**: Database URL
- **Format**: `postgres://user:password@host:port/database`
- **Usage**: Configures the main PostgreSQL database connection
- **Example**: `DATABASE_URL=postgres://profiles_user:password@localhost:5432/profiles_db`

### WORDPRESS_DATABASE_URL
- **Purpose**: WordPress database connection string for legacy integration
- **Type**: Database URL
- **Format**: `mysql://user:password@host:port/database`
- **Usage**: Connects to existing WordPress database for user and content integration
- **Example**: `WORDPRESS_DATABASE_URL=mysql://wp_user:password@localhost:3306/wordpress_db`

### CONN_MAX_AGE
- **Purpose**: Maximum age of database connections in seconds
- **Type**: Integer
- **Default**: 60
- **Usage**: Controls database connection pooling
- **Example**: `CONN_MAX_AGE=60`

### REDIS_SERVER
- **Purpose**: Redis server connection string for caching and sessions
- **Type**: Redis URL
- **Default**: "redis://opensearchlocal:6379"
- **Usage**: Configures Redis for default cache and Select2 widget caching
- **Example**: `REDIS_SERVER=redis://localhost:6379`

## Authentication and Security Variables

### CILOGON_CLIENT_ID
- **Purpose**: OAuth 2.0 client identifier for CILogon authentication
- **Type**: String
- **Default**: ""
- **Usage**: Required for CILogon OAuth integration and user authentication
- **Security**: Sensitive credential that should be kept secure
- **Example**: `CILOGON_CLIENT_ID=cilogon:/client_id/1234`

### CILOGON_CLIENT_SECRET
- **Purpose**: OAuth 2.0 client secret for CILogon authentication
- **Type**: String
- **Default**: ""
- **Usage**: Required for secure OAuth token exchange with CILogon
- **Security**: Highly sensitive credential, must be kept secret
- **Example**: `CILOGON_CLIENT_SECRET=secret_key_here`

### CILOGON_REGISTERED_DOMAIN
- **Purpose**: Domain registered with CILogon for OAuth callbacks
- **Type**: String
- **Default**: "profile.hcommons.org"
- **Usage**: Used in OAuth redirects when the registered domain differs from the actual domain
- **Example**: `CILOGON_REGISTERED_DOMAIN=profile.hcommons.org`

### CILOGON_ACTUAL_DOMAIN
- **Purpose**: Actual domain the instance runs on (if different from registered)
- **Type**: String
- **Default**: ""
- **Usage**: When set, redirects go through REGISTERED_DOMAIN but forward back to ACTUAL_DOMAIN
- **Example**: `CILOGON_ACTUAL_DOMAIN=profile.hcommons-dev.org`

### ALLOWED_CILOGON_FORWARDING_DOMAINS
- **Purpose**: Whitelist of domains allowed for OAuth forwarding
- **Type**: List
- **Default**: ["hcommons.org", "msu.edu", "localhost", "lndo.site", "hcommons-staging.org", "hcommons-dev.org"]
- **Usage**: Security control for OAuth redirect destinations
- **Example**: `ALLOWED_CILOGON_FORWARDING_DOMAINS=hcommons.org,msu.edu`

### STATIC_API_BEARER
- **Purpose**: Bearer token for static API access authentication
- **Type**: String
- **Default**: ""
- **Usage**: Authenticates requests to static API endpoints
- **Security**: Sensitive token that should be rotated regularly
- **Example**: `STATIC_API_BEARER=bearer_token_here`

### TOKEN_ENCRYPTION_KEY
- **Purpose**: Encryption key for tokens stored at rest
- **Type**: String
- **Default**: "" (falls back to STATIC_API_BEARER)
- **Usage**: Used to encrypt OAuth tokens in the database
- **Security**: Should be a strong, randomly generated key
- **Example**: `TOKEN_ENCRYPTION_KEY=encryption_key_here`

### WEBHOOK_TOKEN
- **Purpose**: Token for webhook authentication and validation
- **Type**: String
- **Required**: Yes
- **Usage**: Validates incoming webhook requests for security
- **Security**: Should be a strong, randomly generated token
- **Example**: `WEBHOOK_TOKEN=webhook_secret_token`

### WEBHOOK_URLS
- **Purpose**: List of URLs to send webhook notifications to
- **Type**: List
- **Default**: []
- **Usage**: External services that receive association and profile update notifications
- **Example**: `WEBHOOK_URLS=https://works.example.org/webhook,https://other.example.org/webhook`

### STATS_PASSWORD
- **Purpose**: Password for accessing statistics dashboard
- **Type**: String
- **Default**: ""
- **Usage**: Basic authentication for stats endpoints
- **Security**: Should be a strong password
- **Example**: `STATS_PASSWORD=secure_stats_password`

### VERIFICATION_LIMIT_HOURS
- **Purpose**: Hours before email verification links expire
- **Type**: Integer
- **Default**: 48
- **Usage**: Controls how long users have to verify their email after registration
- **Example**: `VERIFICATION_LIMIT_HOURS=72`

### LOGOUT_ENDPOINTS
- **Purpose**: List of external logout endpoints to call on user logout
- **Type**: List
- **Default**: []
- **Usage**: Enables single logout across multiple applications
- **Example**: `LOGOUT_ENDPOINTS=https://works.example.org/logout`

## External Service Integration Variables

### MLA API Integration

#### MLA_API_KEY
- **Purpose**: API key for Modern Language Association (MLA) service integration
- **Type**: String
- **Default**: ""
- **Usage**: Authenticates requests to MLA API for academic data
- **Security**: Sensitive credential provided by MLA
- **Example**: `MLA_API_KEY=mla_api_key_here`

#### MLA_API_SECRET
- **Purpose**: API secret for MLA service authentication
- **Type**: String
- **Default**: ""
- **Usage**: Used with MLA_API_KEY for secure API authentication
- **Security**: Highly sensitive, must be kept secret
- **Example**: `MLA_API_SECRET=mla_secret_here`

#### MLA_API_BASE_URL
- **Purpose**: Base URL for MLA API
- **Type**: URL
- **Default**: "https://api.mla.org/2/"
- **Usage**: Override for testing or different API versions
- **Example**: `MLA_API_BASE_URL=https://api.mla.org/2/`

### ARLISNA API Integration

#### ARLISNA_API_TOKEN
- **Purpose**: API token for Art Libraries Society of North America integration
- **Type**: String
- **Default**: ""
- **Usage**: Authenticates requests to ARLISNA API
- **Example**: `ARLISNA_API_TOKEN=token_here`

#### ARLISNA_API_BASE_URL
- **Purpose**: Base URL for ARLISNA API
- **Type**: URL
- **Default**: "https://www.arlisna.org/api/"
- **Usage**: Override for testing or different API versions
- **Example**: `ARLISNA_API_BASE_URL=https://www.arlisna.org/api/`

### UP API Integration (Association of American University Presses)

#### UP_API_TOKEN
- **Purpose**: API token for UP integration
- **Type**: String
- **Default**: ""
- **Usage**: Authenticates requests to UP API
- **Example**: `UP_API_TOKEN=token_here`

#### UP_CLIENT_ID
- **Purpose**: OAuth client ID for UP API
- **Type**: String
- **Default**: ""
- **Example**: `UP_CLIENT_ID=client_id_here`

#### UP_CLIENT_SECRET
- **Purpose**: OAuth client secret for UP API
- **Type**: String
- **Default**: ""
- **Security**: Sensitive credential
- **Example**: `UP_CLIENT_SECRET=secret_here`

#### UP_REFRESH_TOKEN
- **Purpose**: OAuth refresh token for UP API
- **Type**: String
- **Default**: ""
- **Usage**: Used to obtain new access tokens
- **Example**: `UP_REFRESH_TOKEN=refresh_token_here`

#### UP_API_BASE_URL
- **Purpose**: Base URL for UP API
- **Type**: URL
- **Default**: "https://www.up.org/api/"
- **Example**: `UP_API_BASE_URL=https://www.up.org/api/`

### Email Service

#### SPARKPOST_API_KEY
- **Purpose**: API key for SparkPost email delivery service
- **Type**: String
- **Default**: ""
- **Usage**: Authenticates email sending through SparkPost
- **Security**: Sensitive credential from SparkPost
- **Example**: `SPARKPOST_API_KEY=sparkpost_key_here`

#### DJANGO_EMAIL_BACKEND
- **Purpose**: Email backend class to use
- **Type**: String
- **Default**: "django.core.mail.backends.smtp.EmailBackend" (base), "django.core.mail.backends.console.EmailBackend" (local)
- **Usage**: Configure email delivery method
- **Example**: `DJANGO_EMAIL_BACKEND=anymail.backends.sparkpost.EmailBackend`

#### DJANGO_DEFAULT_FROM_EMAIL
- **Purpose**: Default sender email address
- **Type**: String
- **Default**: "knowledge-commons-profiles <noreply@hcommons.org>"
- **Example**: `DJANGO_DEFAULT_FROM_EMAIL=noreply@example.org`

#### DJANGO_SERVER_EMAIL
- **Purpose**: Email address for server error notifications
- **Type**: String
- **Default**: Same as DJANGO_DEFAULT_FROM_EMAIL
- **Example**: `DJANGO_SERVER_EMAIL=errors@example.org`

#### DJANGO_EMAIL_SUBJECT_PREFIX
- **Purpose**: Prefix for email subject lines
- **Type**: String
- **Default**: "[knowledge-commons-profiles] "
- **Example**: `DJANGO_EMAIL_SUBJECT_PREFIX=[KC Profiles]`

### Mailchimp Integration

#### MAILCHIMP_API_KEY
- **Purpose**: API key for Mailchimp newsletter integration
- **Type**: String
- **Required**: Yes
- **Security**: Sensitive credential
- **Example**: `MAILCHIMP_API_KEY=your-api-key-here`

#### MAILCHIMP_LIST_ID
- **Purpose**: Mailchimp audience/list ID
- **Type**: String
- **Required**: Yes
- **Usage**: Identifies which Mailchimp list to add subscribers to
- **Example**: `MAILCHIMP_LIST_ID=abc123def4`

#### MAILCHIMP_DC
- **Purpose**: Mailchimp data center identifier
- **Type**: String
- **Required**: Yes
- **Usage**: Part of the Mailchimp API URL (e.g., us1, us2)
- **Example**: `MAILCHIMP_DC=us1`

#### MAILCHIMP_NEWSLETTER_GROUP_ID
- **Purpose**: Group ID for newsletter subscription within the list
- **Type**: String
- **Required**: Yes
- **Usage**: Identifies the newsletter interest group
- **Example**: `MAILCHIMP_NEWSLETTER_GROUP_ID=12345`

### Commons Search Integration

#### CC_SEARCH_URL
- **Purpose**: Base URL for Commons Catalog search API
- **Type**: URL
- **Default**: "https://search.hcommons.org/v1/"
- **Usage**: Configures connection to search service
- **Example**: `CC_SEARCH_URL=https://search.hcommons.org/v1/`

#### CC_SEARCH_ADMIN_KEY
- **Purpose**: Admin API key for Commons Catalog search
- **Type**: String
- **Default**: ""
- **Security**: Sensitive credential
- **Example**: `CC_SEARCH_ADMIN_KEY=admin_key_here`

#### CC_SEARCH_TIMEOUT
- **Purpose**: Timeout in seconds for search API requests
- **Type**: Integer
- **Default**: 10
- **Example**: `CC_SEARCH_TIMEOUT=15`

### Navigation Links

These variables control the sidebar navigation URLs in the application. Override them to point to different services per deployment.

#### NAV_NEWS_FEED_URL
- **Purpose**: URL for the "News Feed" sidebar link
- **Type**: URL
- **Default**: "https://hcommons.org/activity/"
- **Example**: `NAV_NEWS_FEED_URL=https://example.org/activity/`

#### NAV_GROUPS_URL
- **Purpose**: URL for the "Groups" sidebar link
- **Type**: URL
- **Default**: "https://hcommons.org/groups/"
- **Example**: `NAV_GROUPS_URL=https://example.org/groups/`

#### NAV_SITES_URL
- **Purpose**: URL for the "Sites" sidebar link
- **Type**: URL
- **Default**: "https://hcommons.org/sites/"
- **Example**: `NAV_SITES_URL=https://example.org/sites/`

#### NAV_WORKS_URL
- **Purpose**: URL for the "Works" sidebar link
- **Type**: URL
- **Default**: "https://works.hcommons.org/"
- **Example**: `NAV_WORKS_URL=https://works.example.org/`

#### NAV_SUPPORT_URL
- **Purpose**: URL for the "Help & Support" sidebar link
- **Type**: URL
- **Default**: "https://support.hcommons.org/"
- **Example**: `NAV_SUPPORT_URL=https://support.example.org/`

#### NAV_ORGANIZATIONS_URL
- **Purpose**: URL for the "KC Organizations" sidebar link
- **Type**: URL
- **Default**: "https://hcommons.org/societies/"
- **Example**: `NAV_ORGANIZATIONS_URL=https://example.org/societies/`

#### NAV_ABOUT_URL
- **Purpose**: URL for the "About the Commons" sidebar link
- **Type**: URL
- **Default**: "https://sustaining.hcommons.org/"
- **Example**: `NAV_ABOUT_URL=https://sustaining.example.org/`

#### NAV_BLOG_URL
- **Purpose**: URL for the "Team Blog" sidebar link
- **Type**: URL
- **Default**: "https://team.hcommons.org/"
- **Example**: `NAV_BLOG_URL=https://team.example.org/`

### Registration Configuration

#### OPEN_REGISTRATION_NETWORKS
- **Purpose**: Networks that allow open registration without institutional affiliation
- **Type**: List of tuples (code, name)
- **Default**: [("HASTAC", "Humanities, Arts, Science..."), ("SAH", "Society of Architectural Historians"), ("STEMEd+", "STEM Ed+")]
- **Usage**: Controls which networks appear in the registration network selector
- **Example**: Configured in settings, not typically overridden via environment

#### SYNC_HOURS
- **Purpose**: Hours before external syncs are considered stale
- **Type**: Integer
- **Default**: 24
- **Usage**: Controls how often profile data is synced with external services
- **Example**: `SYNC_HOURS=12`

## WordPress Integration Variables

### WP_MEDIA_URL
- **Purpose**: Base URL for WordPress media files
- **Type**: URL
- **Default**: ""
- **Usage**: Configures media file access from WordPress integration
- **Example**: `WP_MEDIA_URL=https://wordpress.example.com/wp-content/uploads/`

### WP_MEDIA_ROOT
- **Purpose**: File system path to WordPress media files
- **Type**: File path
- **Default**: ""
- **Usage**: Local file system access to WordPress media
- **Example**: `WP_MEDIA_ROOT=/var/www/wordpress/wp-content/uploads/`

## AWS S3 Storage Variables

These variables are required for production and dev environments where static and media files are stored in S3.

### DJANGO_AWS_ACCESS_KEY_ID
- **Purpose**: AWS access key for S3 storage
- **Type**: String
- **Required**: Yes (production/dev)
- **Security**: Sensitive credential
- **Example**: `DJANGO_AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE`

### DJANGO_AWS_SECRET_ACCESS_KEY
- **Purpose**: AWS secret key for S3 storage
- **Type**: String
- **Required**: Yes (production/dev)
- **Security**: Highly sensitive credential
- **Example**: `DJANGO_AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

### DJANGO_AWS_STORAGE_BUCKET_NAME
- **Purpose**: S3 bucket name for static and media files
- **Type**: String
- **Required**: Yes (production/dev)
- **Example**: `DJANGO_AWS_STORAGE_BUCKET_NAME=my-profiles-bucket`

### DJANGO_AWS_S3_REGION_NAME
- **Purpose**: AWS region for S3 bucket
- **Type**: String
- **Default**: None
- **Example**: `DJANGO_AWS_S3_REGION_NAME=us-east-1`

### DJANGO_AWS_S3_CUSTOM_DOMAIN
- **Purpose**: Custom domain for S3/CloudFront access
- **Type**: String
- **Default**: None (uses bucket.s3.amazonaws.com)
- **Usage**: Set when using CloudFront or custom domain for static files
- **Example**: `DJANGO_AWS_S3_CUSTOM_DOMAIN=cdn.example.org`

### DJANGO_AWS_S3_MAX_MEMORY_SIZE
- **Purpose**: Maximum in-memory file size before streaming to S3
- **Type**: Integer (bytes)
- **Default**: 100000000 (100MB)
- **Usage**: Files larger than this are streamed rather than loaded into memory
- **Example**: `DJANGO_AWS_S3_MAX_MEMORY_SIZE=50000000`

## Monitoring and Observability Variables

### SENTRY_DSN
- **Purpose**: Data Source Name for Sentry error monitoring
- **Type**: URL
- **Usage**: Configures Sentry SDK for error tracking and performance monitoring
- **Required**: Yes (production/dev environments)
- **Example**: `SENTRY_DSN=https://key@sentry.io/project`

### SENTRY_ENVIRONMENT
- **Purpose**: Environment identifier for Sentry
- **Type**: String
- **Default**: "production" (production), "dev" (development)
- **Usage**: Tags errors and events with the deployment environment
- **Example**: `SENTRY_ENVIRONMENT=staging`

### SENTRY_TRACES_SAMPLE_RATE
- **Purpose**: Sampling rate for Sentry performance tracing
- **Type**: Float (0.0 to 1.0)
- **Default**: 1.0 (100% of transactions)
- **Usage**: Controls what percentage of transactions are sent to Sentry for performance monitoring
- **Example**: `SENTRY_TRACES_SAMPLE_RATE=0.1` (10% sampling)

### DJANGO_SENTRY_LOG_LEVEL
- **Purpose**: Minimum log level for Sentry event capture
- **Type**: Integer (Python logging level)
- **Default**: 20 (logging.INFO)
- **Usage**: Controls which log events are sent to Sentry
- **Example**: `DJANGO_SENTRY_LOG_LEVEL=40` (logging.ERROR)

## Security Best Practices

### Credential Management
- Store sensitive variables in secure environment files
- Use different credentials for each environment
- Rotate API keys and tokens regularly
- Never commit credentials to version control

### Environment File Structure
```
.envs/
├── .local/
│   ├── .django
│   └── .postgres
├── .dev/
│   ├── .django
│   └── .postgres
└── .production/
    ├── .django
    └── .postgres
```

### Variable Validation
- Required variables without defaults will cause startup failures
- Use `env()` function with appropriate defaults for optional variables
- Validate URL formats for database and service connections

### Docker Integration
Variables are passed to containers through:
- AWS secrets manager
- Docker Compose environment configuration
- Container startup scripts

## Troubleshooting

### Common Issues

**Missing Required Variables**
- Error: `ImproperlyConfigured: Set the VARIABLE_NAME environment variable`
- Solution: Add the missing variable to appropriate environment file

**Database Connection Failures**
- Check `DATABASE_URL` format and credentials
- Verify database server accessibility
- Confirm database exists and user has permissions

**Redis Connection Issues**
- Verify `REDIS_SERVER` URL and port
- Check Redis server status
- Confirm network connectivity

**Authentication Failures**
- Validate API keys and secrets are current
- Check token expiration dates
- Verify service account permissions

## Related Documentation

- [Docker Deployment Guide](docker_deployment_guide.md) - Container environment configuration
