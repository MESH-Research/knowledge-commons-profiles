# Dev IDMS (async broker) image.
#
# Built from the same base as the dev django image so the full application is
# available, but runs the broker endpoints under uvicorn (ASGI) instead of
# gunicorn. One process per container: this image only ever runs uvicorn.
ARG ECR_REGISTRY
FROM ${ECR_REGISTRY}/kcprofiles-base:latest

ARG APP_HOME=/app

ENV BUILD_ENV=dev

WORKDIR ${APP_HOME}

RUN addgroup --system --gid 1000 django \
  && adduser --system --uid 1000 --ingroup django django

COPY --chown=django:django ./compose/dev/idms/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY --chown=django:django ./compose/dev/idms/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

# Build/deploy metadata (passed from CI via compose build args) so the running
# container can self-report the deployed branch, image tag and commit SHA.
ARG APP_BRANCH=unknown
ARG BUILD_TAG=unknown
ARG GIT_SHA=unknown
ENV APP_BRANCH=${APP_BRANCH} \
    BUILD_TAG=${BUILD_TAG} \
    GIT_SHA=${GIT_SHA}

USER django

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
