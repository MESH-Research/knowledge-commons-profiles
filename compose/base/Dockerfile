# Base image for Knowledge Commons Profiles
#
# Contains system dependencies, Python venv with all packages installed,
# and uv for runtime sync. Does NOT include app code, entrypoints, or users.
#
# Build variants:
#   production: BUILD_ENVIRONMENT=production -> kcprofiles-base
#   dev/local:  BUILD_ENVIRONMENT=local      -> kcprofiles-base-dev

FROM docker.io/python:3.12.13-slim-bookworm AS python

# Python build stage — compiles native extensions, installs dependencies
FROM python AS python-build-stage

ARG BUILD_ENVIRONMENT=production

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /bin/uv

RUN apt-get update && apt-get install --no-install-recommends -y \
  build-essential \
  libpq-dev \
  libmariadb-dev \
  libmariadb-dev-compat \
  pkg-config

WORKDIR /app

COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-default-groups \
    --group ${BUILD_ENVIRONMENT}


# Python run stage — runtime dependencies only
FROM python AS python-run-stage

ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR ${APP_HOME}

# Install all runtime system dependencies (superset of all environments)
RUN apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  libmariadb-dev \
  libmariadb-dev-compat \
  pkg-config \
  gettext \
  wait-for-it \
  nano \
  rsync \
  curl \
  wget \
  sudo \
  git \
  bash-completion \
  ssh \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# Install uv in the run stage
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

# Copy virtual environment from build stage
COPY --from=python-build-stage /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_NO_CACHE=1
