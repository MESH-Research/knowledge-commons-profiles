# Knowledge Commons Profiles & Identity Management

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) ![Python](https://img.shields.io/badge/python-v3.7+-blue.svg) [![Code style: djlint](https://img.shields.io/badge/html%20style-djlint-blue.svg)](https://www.djlint.com)
![Django](https://img.shields.io/badge/django-3.2+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)


The central user profiles and identity management system for the Knowledge Commons platform, providing secure authentication, user profiles, and organizational role management.

## Overview

Knowledge Commons Profiles serves as both the user profile management system and the Identity Management Stack (IDMS) for the Knowledge Commons ecosystem. Built on Django, it provides:

- **Secure Authentication**: Leveraging CILogon for secure Single Sign-On (SSO) across the Knowledge Commons platform
- **Unified User Profiles**: Centralized user information and preferences
- **Role Management**: Comprehensive system for managing organizational memberships and roles
- **API**: RESTful endpoints for integration with other services

## Key Features

### Authentication & Security
- CILogon-based SSO integration
- Multi-factor authentication support
- OAuth 2.0 and OpenID Connect compliant
- Secure session management

### User Profiles
- Customizable public profiles
- Academic and professional information
- Social media integration
- Privacy controls

### Identity Management
- Centralized user directory
- Role-based access control
- Organization and group management
- Audit logging

### API Endpoints
- User management
- Authentication flows
- Profile data access
- Role and permission management

## Getting Started

### Prerequisites

- Python 3.7+
- PostgreSQL 12+
- Redis
- Docker (for containerized deployment)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/MESH-Research/knowledge-commons-profiles.git
   cd knowledge-commons-profiles
   ```

2. Set up a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/local.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Development

### Code Style

This project uses:
- [Ruff](https://github.com/charliermarsh/ruff) for Python linting
- [djLint](https://www.djlint.com/) for HTML template linting
- [Pre-commit](https://pre-commit.com/) for git hooks

Set up pre-commit hooks:
```bash
pre-commit install
```

### Testing

Run the test suite:
```bash
pytest
```

### Documentation

Build documentation locally:
```bash
cd docs
make html
```

## Deployment

### Production

The application is designed to be deployed using Docker Compose:

```bash
docker-compose -f production.yml up -d
```

### Environment Variables

Key environment variables:

- `DJANGO_SECRET_KEY`: Required for production
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection URL
- `CILOGON_CLIENT_ID`: CILogon OAuth client ID
- `CILOGON_CLIENT_SECRET`: CILogon OAuth client secret

## API Documentation

API documentation is available at `/api/docs/` when running the development server.

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue in the [issue tracker](https://github.com/MESH-Research/knowledge-commons-profiles/issues).

## Acknowledgments

- Built with [Cookiecutter Django](https://github.com/cookiecutter/cookiecutter-django/)
- Uses [CILogon](https://www.cilogon.org/) for secure authentication
- Inspired by the needs of the academic community
