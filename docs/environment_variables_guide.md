# Environment Variables Technical Guide

> **Version Note**: This documentation is for knowledge-commons-profiles version 2.30.0

## Overview

This guide documents the environment variables used for application startup and configuration in the Profiles App. Environment variables provide a secure and flexible way to configure the application across different deployment environments (local, development, production) without hardcoding sensitive values.

## Core Application Variables

### USE_DOCKER
- **Purpose**: Flag to indicate if the application is running in a Docker environment
- **Type**: String ("yes" or "no")
- **Default**: "no"
- **Usage**: Used in local settings to configure internal IPs for Django Debug Toolbar when running in Docker containers
- **Example**: `USE_DOCKER=yes`

### DJANGO_DEBUG
- **Purpose**: Controls Django's debug mode
- **Type**: Boolean
- **Default**: False (production), True (local/development)
- **Usage**: Enables detailed error pages, debug toolbar, and development features
- **Security**: Must be False in production environments
- **Example**: `DJANGO_DEBUG=True`

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
- **Usage**: Required for CILogon OAuth integration and user authentication
- **Security**: Sensitive credential that should be kept secure
- **Example**: `CILOGON_CLIENT_ID=cilogon:/client_id/1234`

### CILOGON_CLIENT_SECRET
- **Purpose**: OAuth 2.0 client secret for CILogon authentication
- **Type**: String
- **Usage**: Required for secure OAuth token exchange with CILogon
- **Security**: Highly sensitive credential, must be kept secret
- **Example**: `CILOGON_CLIENT_SECRET=secret_key_here`

### STATIC_API_BEARER
- **Purpose**: Bearer token for static API access authentication
- **Type**: String
- **Usage**: Authenticates requests to static API endpoints
- **Security**: Sensitive token that should be rotated regularly
- **Example**: `STATIC_API_BEARER=bearer_token_here`

### WEBHOOK_TOKEN
- **Purpose**: Token for webhook authentication and validation
- **Type**: String
- **Usage**: Validates incoming webhook requests for security
- **Security**: Should be a strong, randomly generated token
- **Example**: `WEBHOOK_TOKEN=webhook_secret_token`

### STATS_PASSWORD
- **Purpose**: Password for accessing statistics dashboard
- **Type**: String
- **Usage**: Basic authentication for stats endpoints
- **Security**: Should be a strong password
- **Example**: `STATS_PASSWORD=secure_stats_password`

## External Service Integration Variables

### MLA_API_KEY
- **Purpose**: API key for Modern Language Association (MLA) service integration
- **Type**: String
- **Usage**: Authenticates requests to MLA API for academic data
- **Security**: Sensitive credential provided by MLA
- **Example**: `MLA_API_KEY=mla_api_key_here`

### MLA_API_SECRET
- **Purpose**: API secret for MLA service authentication
- **Type**: String
- **Usage**: Used with MLA_API_KEY for secure API authentication
- **Security**: Highly sensitive, must be kept secret
- **Example**: `MLA_API_SECRET=mla_secret_here`

### SPARKPOST_API_KEY
- **Purpose**: API key for SparkPost email delivery service
- **Type**: String
- **Usage**: Authenticates email sending through SparkPost
- **Security**: Sensitive credential from SparkPost
- **Example**: `SPARKPOST_API_KEY=sparkpost_key_here`

## WordPress Integration Variables

### WP_MEDIA_URL
- **Purpose**: Base URL for WordPress media files
- **Type**: URL
- **Usage**: Configures media file access from WordPress integration
- **Example**: `WP_MEDIA_URL=https://wordpress.example.com/wp-content/uploads/`

### WP_MEDIA_ROOT
- **Purpose**: File system path to WordPress media files
- **Type**: File path
- **Usage**: Local file system access to WordPress media
- **Example**: `WP_MEDIA_ROOT=/var/www/wordpress/wp-content/uploads/`

## Development and Debugging Variables

### IPYTHONDIR
- **Purpose**: Directory for IPython configuration
- **Type**: File path
- **Status**: Not found in current codebase
- **Usage**: Would configure IPython shell directory if used
- **Example**: `IPYTHONDIR=/app/.ipython`

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
