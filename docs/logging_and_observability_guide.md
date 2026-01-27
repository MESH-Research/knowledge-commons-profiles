# Logging and Observability Technical Guide

> **Note**: This documentation refers to knowledge-commons-profiles version 3.15.0

## Overview

The knowledge-commons-profiles application implements a robust logging and observability strategy using structured JSON logging, Sentry for error monitoring, and AWS CloudWatch for log aggregation. The system provides detailed request tracing, exception handling, and performance monitoring across development, staging, and production environments.

## Logging Architecture

### Structured JSON Logging

The application uses structured JSON logging to provide consistent, searchable log output that integrates with cloud-based log aggregation services.

#### Core Components

**Custom JSON Formatter** (`log_config/error_formatter.py`)
- `StructuredExceptionJsonFormatter`: Extends `pythonjsonlogger.json.JsonFormatter`
- Automatically structures exception information into JSON format
- Extracts exception type, value, and full traceback for debugging
- Removes raw exception info to prevent log pollution

**Context Filter** (`log_config/log_context.py`)
- `ContextFilter`: Adds contextual information to every log record
- Injects hostname and process ID for multi-instance deployments
- Generates unique request IDs for request tracing
- Supports custom context variables through `contextvars`
- Integrates with Django's thread-local request storage

#### Request Tracing

The logging system implements request tracing:

**Request ID Generation**
- Automatic UUID generation for each request
- Support for external request IDs via `X-Request-ID` header
- Request ID propagation across all log messages within a request
- Integration with middleware for tracking

**Context Variables**
- Thread-safe context storage using Python's `contextvars`
- Custom context injection for business logic tracking
- Automatic context cleanup between requests

### Environment-Specific Configuration

#### Production Configuration (`log_config/prod.yaml`)

```yaml
formatters:
  json_formatter:
    (): log_config.error_formatter.StructuredExceptionJsonFormatter
    format: "%(asctime)s %(name)s %(levelname)s %(message)s"
    rename_fields:
      levelname: level
      asctime: time

filters:
  add_context:
    (): log_config.log_context.ContextFilter

handlers:
  console:
    class: logging.StreamHandler
    formatter: json_formatter
    level: DEBUG
    filters: [add_context]
```

**Key Features**:
- JSON-structured output for AWS CloudWatch integration
- Field renaming for consistent log schema
- Context filtering for request tracing
- Console output for containerized environments

#### Development Configuration (`log_config/dev.yaml`)

**Enhanced Logging Levels**:
- Application logs: `DEBUG` level for detailed debugging
- Database queries: `ERROR` level to reduce noise
- Sentry SDK: `ERROR` level for integration debugging
- Security events: `ERROR` level for Django security logging

**Additional Loggers**:
- `django.db.backends`: Database query logging
- `sentry_sdk`: Sentry integration debugging
- `django.security.DisallowedHost`: Security event logging

#### Local Development Configuration (`log_config/local.yaml`)

Similar to development configuration but optimized for local debugging with enhanced console output and reduced log volume for better developer experience.

## Sentry Error Monitoring

Sentry is a real-time error tracking and performance monitoring platform that provides detailed insights into application errors, performance issues, and user impact. It automatically captures exceptions, tracks error frequency and trends, and provides rich context including stack traces, user sessions, and environmental data to help developers quickly identify and resolve issues.

The knowledge-commons-profiles application uses Sentry across all environments to monitor application health and provide immediate visibility into production issues. Sentry's web interface allows developers and operations teams to browse errors, set up alerts, track releases, and monitor application performance. The platform integrates directly with the application's logging system to provide automatic error capture and detailed debugging information.

## Sentry Integration

### Production Sentry Configuration

**Integration Setup** (`config/settings/production.py`)
```python
sentry_logging = LoggingIntegration(
    level=SENTRY_LOG_LEVEL,
    event_level=logging.ERROR,
)
integrations = [
    sentry_logging,
    DjangoIntegration(),
    RedisIntegration(),
    LoggingIntegration(sentry_logs_level=logging.DEBUG),
]
sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=integrations,
    environment=env("SENTRY_ENVIRONMENT", default="production"),
    traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=1.0),
    _experiments={"enable_logs": True},
)
```

**Key Features**:
- **Error Event Capture**: Automatic capture of ERROR level events
- **Breadcrumb Collection**: INFO level and above captured as breadcrumbs
- **Django Integration**: Automatic Django request/response tracking
- **Redis Integration**: Redis operation monitoring
- **Performance Monitoring**: Configurable trace sampling
- **Log Forwarding**: Experimental log forwarding to Sentry

### Development Sentry Configuration

**Simplified Setup** (`config/settings/dev.py`)
- Reduced integration complexity for development
- Same error capture capabilities
- Environment-specific tagging for issue separation

### Sentry Usage Throughout Application

**Explicit Exception Capture**
The application uses explicit Sentry capture in critical error paths:

**OAuth Error Handling** (`cilogon/views.py`)
```python
except OAuthError as e:
    sentry_sdk.capture_exception()
    logger.exception("OAuth authentication failed")
```

**Database Operation Failures** (`cilogon/middleware.py`)
```python
except OperationalError:
    logger.exception("Database operational error during garbage collection")
    sentry_sdk.capture_exception()
```

**External API Integration** (`cilogon/sync_apis/mla.py`)
```python
except ValidationError:
    logger.exception("Error parsing MLA search response")
    sentry_sdk.capture_exception()
```

## AWS CloudWatch Integration

### Log Aggregation Strategy

**Container Logging**
- Application logs output to STDOUT/STDERR
- Docker containers configured for log forwarding
- AWS CloudWatch Logs agent collects container output
- Structured JSON format enables CloudWatch Insights queries

**Log Groups Organization**
- Environment-specific log groups (production, staging, development)
- Application-specific log streams
- Retention policies configured per environment

**CloudWatch Insights Queries**
The structured JSON format enables powerful log analysis:

```sql
fields @timestamp, level, message, request_id, hostname
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**Request Tracing Queries**
```sql
fields @timestamp, message, request_id
| filter request_id = "specific-request-id"
| sort @timestamp asc
```

### Performance Monitoring

**Application Metrics**
- Request duration tracking through middleware
- Database query performance monitoring
- External API response time tracking
- Cache hit/miss ratio monitoring

**Infrastructure Metrics**
- Container resource utilization
- Database connection pool metrics
- Redis cache performance
- Load balancer health checks

## Logging Best Practices

### Application-Level Logging

**Structured Logging Implementation**
```python
import logging
import sentry_sdk

logger = logging.getLogger(__name__)

# Good: Structured logging with context
logger.info(
    "User profile updated",
    extra={
        "user_id": user.id,
        "profile_fields": ["name", "email"],
        "update_source": "api"
    }
)

# Error handling with Sentry integration
try:
    risky_operation()
except Exception as e:
    logger.exception("Operation failed with context")
    sentry_sdk.capture_exception()
    raise
```

**Log Level Guidelines**
- **DEBUG**: Detailed debugging information, disabled in production
- **INFO**: General application flow and business logic events
- **WARNING**: Recoverable errors or unexpected conditions
- **ERROR**: Error conditions that require attention
- **CRITICAL**: Severe errors that may cause application failure

### Security and Privacy

**Sensitive Data Handling**
- Automatic sanitization of email addresses in development
- PII redaction in log messages
- Secure handling of authentication tokens
- GDPR-compliant logging practices

**Log Retention Policies**
- Production logs: 90-day retention
- Development logs: 30-day retention
- Error logs: Extended retention for compliance
- Automatic log rotation and cleanup

## Monitoring and Alerting

### Sentry Alerting

**Error Rate Monitoring**
- Automatic alerts for error rate spikes
- Environment-specific alert thresholds
- Integration with team communication tools
- Escalation policies for critical errors

**Performance Monitoring**
- Transaction performance tracking
- Database query performance alerts
- External service dependency monitoring
- Custom metric tracking for business logic

### CloudWatch Alarms

**Infrastructure Monitoring**
- Container health and resource utilization
- Database connection and performance metrics
- Cache performance and availability
- Load balancer and network metrics

**Application Monitoring**
- Error rate thresholds
- Response time monitoring
- Custom business metric alerts
- Log-based metric extraction

## Development and Debugging

### Local Development Setup

**Log Configuration**
- Human-readable console output for development
- Reduced log volume for better developer experience
- Debug-level logging for application components
- Integration with Django debug toolbar

**Testing Logging**
- Separate test logging configuration
- Log capture for test debugging
- Performance profiling integration
- Mock external service logging

### Production Debugging

**Log Analysis Tools**
- CloudWatch Insights for complex queries
- Sentry for error investigation and user impact analysis
- Request tracing for performance debugging
- Correlation between logs and metrics

**Troubleshooting Workflows**
1. **Error Investigation**: Start with Sentry error details
2. **Request Tracing**: Use request ID to trace full request lifecycle
3. **Performance Analysis**: Correlate logs with CloudWatch metrics
4. **Root Cause Analysis**: Combine application logs with infrastructure metrics

## Configuration Management

### Environment Variables

**Required Settings**
- `SENTRY_DSN`: Sentry project DSN for error reporting
- `SENTRY_ENVIRONMENT`: Environment tag for Sentry events
- `SENTRY_TRACES_SAMPLE_RATE`: Performance monitoring sample rate
- `DJANGO_SENTRY_LOG_LEVEL`: Minimum log level for Sentry capture

**Optional Settings**
- `DJANGO_LOG_LEVEL`: Override default application log level
- `X-Request-ID`: External request ID header support
- Log retention and rotation settings

### Deployment Considerations

**Container Configuration**
- Log driver configuration for CloudWatch integration
- Environment-specific log routing
- Resource allocation for logging overhead
- Health check integration with logging system

**Security Configuration**
- Secure transmission of logs to CloudWatch
- IAM roles and permissions for log access
- Encryption at rest and in transit
- Access control for sensitive log data

## Troubleshooting Common Issues

### Log Volume Management

**High Volume Scenarios**
- Debug level logging in production causing volume spikes
- Chatty external service integrations
- Database query logging in high-traffic periods
- Recursive error logging scenarios

**Solutions**
- Dynamic log level adjustment
- Sampling for high-frequency events
- Circuit breaker patterns for external services
- Log rate limiting for specific components

### Performance Impact

**Logging Overhead**
- JSON serialization performance impact
- Network latency for log transmission
- Storage costs for high-volume logging
- Processing overhead for structured logging

**Optimization Strategies**
- Asynchronous log processing
- Batch log transmission
- Selective field inclusion
- Compression for log transport

### Integration Issues

**Sentry Integration Problems**
- Network connectivity issues
- Rate limiting and quota management
- SDK version compatibility
- Environment configuration mismatches

**CloudWatch Integration Issues**
- IAM permission problems
- Log group configuration errors
- Network connectivity from containers
- Log format parsing issues

This logging and observability system provides the foundation for maintaining, debugging, and monitoring the knowledge-commons-profiles application across all environments while ensuring security, performance, and compliance requirements are met.
