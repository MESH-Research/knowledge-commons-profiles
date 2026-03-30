# GitHub CI Django image — uses pre-built dev base from ECR
ARG ECR_REGISTRY
FROM ${ECR_REGISTRY}/kcprofiles-base-dev:latest

ARG APP_HOME=/app

ENV PYTHONPATH="${PYTHONPATH}:${APP_HOME}"

WORKDIR ${APP_HOME}

# Create devcontainer user and add it to sudoers
RUN groupadd --gid 1000 dev-user \
  && useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user \
  && echo dev-user ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/dev-user \
  && chmod 0440 /etc/sudoers.d/dev-user

COPY ./compose/github/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/github/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copy application code to WORKDIR
COPY . ${APP_HOME}

ENTRYPOINT ["/entrypoint"]
