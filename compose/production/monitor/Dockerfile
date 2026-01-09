# Lightweight Python image for website monitoring
FROM docker.io/python:3.12.12-slim-bookworm

ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR ${APP_HOME}

# Install AWS CLI and required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    requests \
    django-environ

# Create non-root user
RUN addgroup --system monitor \
    && adduser --system --ingroup monitor monitor

# Copy only the cron module needed for monitoring
COPY --chown=monitor:monitor ./knowledge_commons_profiles/cron ${APP_HOME}/cron

# Copy entrypoint and start scripts
COPY --chown=monitor:monitor ./compose/production/monitor/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

COPY --chown=monitor:monitor ./compose/production/monitor/start /start
RUN sed -i 's/\r$//g' /start && chmod +x /start

# Make monitor owner of WORKDIR
RUN chown -R monitor:monitor ${APP_HOME}

USER monitor

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
