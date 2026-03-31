# Knowledge Commons Profiles & Identity Management

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) ![Python](https://img.shields.io/badge/python-v3.12+-blue.svg) [![Code style: djlint](https://img.shields.io/badge/html%20style-djlint-blue.svg)](https://www.djlint.com)
![Django](https://img.shields.io/badge/django-5.1+-green.svg)
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

- Python 3.12+
- PostgreSQL 12+
- Redis
- Docker (for containerized deployment)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Local Development with Docker

The recommended way to run the project locally is with Docker via the provided
Makefile. This builds everything locally without needing AWS ECR credentials.

1. Clone the repository:
   ```bash
   git clone https://github.com/MESH-Research/knowledge-commons-profiles.git
   cd knowledge-commons-profiles
   ```

2. Create your environment file:
   ```bash
   cp .envs/.local/.django.example .envs/.local/.django
   # Edit with your configuration
   ```

3. Ensure you have SSL certificates at `~/cert.pem` and `~/key.pem`
   (self-signed is fine for local development).

4. Build and start:
   ```bash
   make build   # builds base image + local Django container
   make up      # starts the server at https://localhost
   ```

Run `make help` to see all available targets:

| Target       | Description                                          |
|--------------|------------------------------------------------------|
| `build`      | Build everything (base image + local app)            |
| `build-base` | Build the base dev image locally (no ECR needed)     |
| `build-app`  | Build the local Django image (requires base image)   |
| `up`         | Start the local dev server (https://localhost)       |
| `down`       | Stop all containers                                  |
| `restart`    | Restart all containers                               |
| `logs`       | Tail container logs                                  |
| `shell`      | Open a bash shell in the running Django container    |
| `manage`     | Run a manage.py command (`make manage CMD="migrate"`)|
| `migrate`    | Run database migrations                              |
| `test`       | Run the test suite inside the container              |
| `lint`       | Run pre-commit hooks on all files                    |
| `clean`      | Remove containers, volumes, and local images         |

### Without Docker

1. Install dependencies:
   ```bash
   uv sync --group local
   ```

2. Configure environment variables:
   ```bash
   cp .envs/.local/.django.example .envs/.local/.django
   # Edit with your configuration
   ```

3. Run migrations:
   ```bash
   uv run python manage.py migrate
   ```

4. Start the development server:
   ```bash
   uv run python manage.py runserver_plus 0.0.0.0:443 \
     --cert-file ~/cert.pem --key-file ~/key.pem
   ```

## Development

### Code Style

This project uses:
- [Ruff](https://github.com/charliermarsh/ruff) for Python linting
- [djLint](https://www.djlint.com/) for HTML template linting
- [Pre-commit](https://pre-commit.com/) for git hooks

Set up pre-commit hooks:
```bash
uv run pre-commit install
```

### Testing

Run the test suite:
```bash
# On the host (requires local Python/DB setup)
DJANGO_SETTINGS_MODULE=config.settings.test \
DJANGO_READ_DOT_ENV_FILE=True \
uv run python manage.py test

# Or inside Docker
make test
```

### Docker Architecture

The project uses a multi-stage base image pattern:

- **`compose/base/Dockerfile`** builds a reusable base image with all system
  and Python dependencies.
- Environment-specific Dockerfiles in `compose/{local,dev,production,github}/`
  layer on top of the base image with entrypoints and configuration.
- `make build-base` builds the base image locally, tagged so the local
  Dockerfile can resolve it without ECR access.

## Deployment

### Production

The application is deployed using Docker Compose:

```bash
docker compose -f docker-compose.production.yml up -d
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
