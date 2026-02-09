# Docker Configuration and Deployment Guide

> **Note**: This documentation refers to knowledge-commons-profiles version 3.15.0

## Overview

The knowledge-commons-profiles application uses Docker for containerized deployment across multiple environments. The application employs a multi-stage Docker build process, environment-specific configurations, and orchestration through Docker Compose. The deployment architecture supports local development, staging, and production environments with appropriate security and performance optimizations for each.

## Docker Architecture

### Multi-Stage Build Process

The application uses a multi-stage Docker build to optimize image size and security:

**Build Stage** (`python-build-stage`)
- Based on Python 3.12.12 slim-bookworm (local/production) or 3.12.9 (dev/github)
- Installs build dependencies for Python packages
- Creates Python dependency wheels for faster installation
- Includes PostgreSQL and MySQL client libraries

**Runtime Stage** (`python-run-stage`)
- Clean runtime environment without build tools
- Installs only runtime dependencies
- Creates non-root `django` user for security
- Copies pre-built wheels from build stage

### Container Images

**Django Application Container**
- **Base Image**: `python:3.12.12-slim-bookworm` (production/local)
- **Platform**: `linux/arm64` (configurable)
- **User**: Non-root `django` user
- **Working Directory**: `/app`
- **Entry Point**: Custom start script

**PostgreSQL Container**
- **Base Image**: `postgres:16`
- **Maintenance Scripts**: Custom backup and restore utilities
- **Data Persistence**: Named volumes for data storage

**Traefik Load Balancer**
- **Base Image**: `traefik:3.3.4`
- **SSL/TLS**: Automatic certificate management with Let's Encrypt
- **Configuration**: YAML-based routing and middleware

## Environment Configurations

### Production Environment

**Docker Compose**: `docker-compose.production.yml`

**Key Features**:
- Multi-platform builds for ARM64 architecture
- ECR registry integration for AWS deployment
- Minimal service configuration for security
- Traefik load balancer with SSL termination
- Named volumes for persistent data

**Services**:
- `django`: Application server with Gunicorn
- `traefik`: Load balancer and SSL termination
- `monitor`: Website monitoring service (see Monitor Service section below)

**Environment Files**:
- `.envs/.production/.django`: Django application settings

### Development Environment

**Docker Compose**: `docker-compose.dev.yml`

**Key Features**:
- Full development stack with database and cache
- ECR registry support for CI/CD integration
- Development-optimized configurations
- Service dependencies and health checks

**Services**:
- `django`: Application server with development settings
- `postgres`: PostgreSQL database with persistent storage
- `redis`: Cache and session storage
- `traefik`: Development load balancer

**Environment Files**:
- `.envs/.dev/.django`: Django development settings
- `.envs/.dev/.postgres`: PostgreSQL configuration

### Local Development Environment

**Docker Compose**: `docker-compose.local.yml`

**Key Features**:
- Volume mounting for live code reloading
- Direct port exposure for debugging
- Simplified service configuration
- Local development optimizations

**Services**:
- `django`: Application server with volume mounts
- Direct port mapping to `localhost:8000`

**Environment Files**:
- `.envs/.local/.django`: Local development settings

## Container Configuration

### Django Application Container

**Dockerfile**: `compose/production/django/Dockerfile`

**Build Process**:
1. **Dependency Installation**: System packages for PostgreSQL and MySQL
2. **Python Dependencies**: Wheel-based installation for faster builds
3. **Security Setup**: Non-root user creation and permission management
4. **Application Deployment**: Code copying and ownership configuration
5. **Entry Point Configuration**: Custom startup scripts

**Runtime Configuration**:
- **Python Settings**: Unbuffered output, no bytecode generation
- **User Context**: Non-root `django` user for security
- **Working Directory**: `/app` for application code
- **Entry Point**: `/start` script for application startup

**System Dependencies**:
- PostgreSQL client libraries (`libpq-dev`)
- MySQL client libraries (`libmariadb-dev`)
- Translation tools (`gettext`)
- Process management utilities (`wait-for-it`)

### Monitor Service Container

**Dockerfile**: `compose/production/monitor/Dockerfile`

The monitor service is a lightweight container for website monitoring tasks:

**Features**:
- Python 3.12.12 slim-bookworm base image
- AWS CLI for CloudWatch metrics publishing
- Minimal dependencies (requests, django-environ)
- Non-root `monitor` user for security
- Runs cron-based monitoring scripts

**Purpose**:
- Website availability monitoring
- Health check execution
- CloudWatch metrics publishing
- Automated alerting integration

**Configuration**:
- Copies the `cron` module from the main application
- Runs independently of the main Django container
- Restarts automatically unless stopped

### Startup Scripts

**Entry Point Script** (`compose/production/django/entrypoint`)
- Basic container initialization
- Error handling configuration
- Command execution delegation

**Start Script** (`compose/production/django/start`)
- Static file collection (`collectstatic`)
- Gunicorn server startup with production settings
- Bind configuration: `0.0.0.0:5000`
- Timeout configuration: 30 seconds

### Traefik Configuration

**Dockerfile**: `compose/production/traefik/Dockerfile`

**Features**:
- Let's Encrypt certificate management
- ACME challenge handling
- Custom configuration injection
- Security-focused file permissions

## Environment Variables

### Django Container Variables

**Required Settings**:
- `DJANGO_SECRET_KEY`: Application secret key
- `DJANGO_SETTINGS_MODULE`: Settings module selection
- `DATABASE_URL`: Database connection string
- `REDIS_SERVER`: Cache server configuration

**AWS Integration**:
- `DJANGO_AWS_ACCESS_KEY_ID`: AWS access credentials
- `DJANGO_AWS_SECRET_ACCESS_KEY`: AWS secret key
- `DJANGO_AWS_STORAGE_BUCKET_NAME`: S3 bucket for static files
- `DJANGO_AWS_S3_REGION_NAME`: AWS region configuration

**External Services**:
- `SENTRY_DSN`: Error monitoring configuration
- `SPARKPOST_API_KEY`: Email service integration
- `CILOGON_CLIENT_ID`: Authentication service credentials
- `CILOGON_CLIENT_SECRET`: OAuth client secret

### Database Variables

**PostgreSQL Configuration**:
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_HOST`: Database host
- `POSTGRES_PORT`: Database port

## Deployment Workflows

### Local Development Deployment

**Prerequisites**:
- Docker and Docker Compose installed
- Environment files configured in `.envs/.local/`

**Deployment Steps**:
```bash
# Build and start local development environment
docker-compose -f docker-compose.local.yml up --build

# Access application at http://localhost:8000
```

**Development Features**:
- Live code reloading through volume mounts
- Direct database access for debugging
- Simplified logging and debugging

### Production Deployment

**Prerequisites**:
- Production environment variables configured
- ECR registry access (if using AWS)
- SSL certificates and domain configuration

**Build Process**:
```bash
# Build production images
docker-compose -f docker-compose.production.yml build

# Deploy with environment-specific configuration
docker-compose -f docker-compose.production.yml up -d
```

**Production Features**:
- Multi-stage builds for optimized image size
- Non-root user execution for security
- SSL termination through Traefik
- Persistent data storage

### CI/CD Integration

**GitHub Actions Integration**:
- Automated builds on code changes
- ECR registry push for deployment
- Environment-specific deployments
- Health check validation

**Image Tagging Strategy**:
- `latest`: Most recent stable build
- `${IMAGE_TAG}`: Version-specific tags
- Environment-specific naming conventions

## Security Considerations

### Container Security

**User Management**:
- Non-root user execution (`django` user)
- Proper file ownership and permissions
- Minimal system access privileges

**Image Security**:
- Minimal base images (slim-bookworm)
- Regular security updates
- Dependency vulnerability scanning

**Network Security**:
- Internal service communication
- SSL/TLS encryption through Traefik
- Firewall-friendly port configuration

### Secrets Management

**Environment Variables**:
- Secure environment file handling
- Separation of development and production secrets
- AWS Secrets Manager integration (production)

**Database Security**:
- Encrypted connections
- Strong password policies
- Network isolation

## Performance Optimization

### Build Optimization

**Multi-Stage Builds**:
- Separate build and runtime environments
- Wheel-based Python dependency installation
- Layer caching for faster rebuilds

**Image Size Reduction**:
- Minimal base images
- Dependency cleanup after installation
- Optimized file copying strategies

### Runtime Optimization

**Application Server**:
- Gunicorn with appropriate worker configuration
- Static file serving through CDN (production)
- Database connection pooling

**Resource Management**:
- Memory limits and CPU constraints
- Health check configurations
- Graceful shutdown handling

## Monitoring and Logging

### Container Monitoring

**Health Checks**:
- Application health endpoints
- Database connectivity verification
- Service dependency validation

**Log Management**:
- Structured JSON logging to STDOUT
- Log aggregation through Docker logging drivers
- AWS CloudWatch integration (production)

### Performance Monitoring

**Application Metrics**:
- Request/response time tracking
- Error rate monitoring
- Resource utilization metrics

**Infrastructure Metrics**:
- Container resource usage
- Network performance
- Storage utilization

## Troubleshooting

### Common Issues

**Build Failures**:
- Dependency installation errors
- Network connectivity issues during build
- Platform compatibility problems

**Runtime Issues**:
- Database connection failures
- Environment variable configuration errors
- File permission problems

**Deployment Issues**:
- Image registry authentication
- Load balancer configuration
- SSL certificate problems

### Debugging Strategies

**Container Inspection**:
```bash
# View container logs
docker-compose logs django

# Execute commands in running container
docker-compose exec django bash

# Inspect container configuration
docker inspect <container_id>
```

**Environment Validation**:
- Verify environment file configurations
- Check service connectivity
- Validate external service access

**Performance Debugging**:
- Monitor resource utilization
- Analyze application logs
- Profile database queries

### Recovery Procedures

**Database Recovery**:
- Backup and restore procedures
- Data migration strategies
- Rollback procedures

**Application Recovery**:
- Container restart procedures
- Configuration rollback
- Health check validation

This Docker deployment guide provides the foundation for deploying and managing the knowledge-commons-profiles application across different environments while maintaining security, performance, and operational best practices.
