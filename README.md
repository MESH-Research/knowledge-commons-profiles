# knowledge-commons-profiles

The profiles system for Knowledge Commons

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) ![Python](https://img.shields.io/badge/python-v3.7+-blue.svg) [![Code style: djlint](https://img.shields.io/badge/html%20style-djlint-blue.svg)](https://www.djlint.com)
![Django](https://img.shields.io/badge/django-3.2+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
![Last Commit](https://img.shields.io/github/last-commit/MESH-Research/knowledge-commons-profiles) ![coverage](https://img.shields.io/endpoint?style=flat-square&url=https://gist.githubusercontent.com/MartinPaulEve/0ed9af78da10972471ef6bf61524ba5e/raw/knowledge-commons-profiles-lcov-coverage.json)

License: [MIT](LICENSE)

**This project is a work in progress and not complete.**

This project provides API endpoints and HTML templated responses to retrieve detailed information about users in our system.

## Features

- Retrieves comprehensive user information including:
  - Personal details (name, title, affiliation)
  - Academic background and interests
  - Publications and projects
  - Social media handles and website URLs
  - Commons activity and memberships
  - And more...

## Settings

Moved to [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).

## Basic Commands

### Setting Up Your Users

- To create a **superuser account**, use this command:

      $ python manage.py createsuperuser


### Type checks

Running type checks with mypy:

    $ mypy knowledge_commons_profiles

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    $ coverage run -m pytest
    $ coverage html
    $ open htmlcov/index.html

#### Running tests with pytest

    $ pytest

### Live reloading and Sass CSS compilation

Moved to [Live reloading and SASS compilation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally.html#using-webpack-or-gulp).

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.
