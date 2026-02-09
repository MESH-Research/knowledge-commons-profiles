# Knowledge Commons Profiles Documentation

> **Note**: This documentation refers to knowledge-commons-profiles version 3.15.0

The Knowledge Commons Profiles application is a Django-based user profile management system that provides authentication, profile management, and integration with external services. The application supports federated identity management through CILogon, integrates with WordPress systems, and provides robust logging and monitoring capabilities.

This documentation provides technical guides for developers, system administrators, and operations teams working with the Knowledge Commons Profiles application.

## Documentation Index

### Authentication and Identity Management

- **[CILogon Features Technical Guide](cilogon/cilogon_features_technical_guide.md)** - Technical overview of CILogon OAuth 2.0/OpenID Connect integration, including authentication flows, user registration, token management, and security features.

- **[CILogon OAuth Flow Diagram](cilogon/cilogon_oauth_flow_diagram.md)** - Visual architecture diagram showing the complete OAuth authentication flow between users, CILogon, and the Knowledge Commons ecosystem including Works and WordPress integration.

- **[CILogon Proxy and Forwarding Guide](cilogon/cilogon_proxy_guide.md)** - How to configure OAuth proxy for staging/development environments and service forwarding for ecosystem integration with KC Works and other services.

### Profile Management

- **[Profiles App Technical Guide](newprofile/profiles_app_technical_guide.md)** - Technical documentation for the core profile management system, covering data models, views, API layer, forms, and integration points with WordPress and external services.

### Configuration and Environment

- **[Environment Variables Guide](environment_variables_guide.md)** - Application startup and configuration variables

### Operations and Monitoring

- **[Logging and Observability Guide](logging_and_observability_guide.md)** - Documentation of the logging and observability infrastructure, including structured JSON logging, Sentry error monitoring, AWS CloudWatch integration, and troubleshooting guides.

### Deployment and Infrastructure

- **[Docker Deployment Guide](docker_deployment_guide.md)** - Docker configuration and deployment documentation covering multi-stage builds, environment-specific configurations, container orchestration, security considerations, and troubleshooting for local, development, and production environments.

## Getting Started

For developers new to the Knowledge Commons Profiles application:

1. Start with the **CILogon Features Technical Guide** to understand the authentication system
2. Review the **Profiles App Technical Guide** to understand the core profile management functionality  
3. Consult the **Logging and Observability Guide** for monitoring and debugging information
4. Reference the **CILogon OAuth Flow Diagram** for a visual overview of the authentication architecture

## Contributing to Documentation

When updating documentation:

- Ensure version numbers match the current application version in `pyproject.toml`
- Avoid marketing language like "comprehensive" or "seamless" - these are technical documents
- Do not include specific code line numbers as they become outdated quickly
- Focus on architectural concepts, data flows, and integration patterns
- Include troubleshooting information and common issues where relevant

## Support

For technical support or questions about the Knowledge Commons Profiles application, consult the relevant technical guide or contact the development team.
