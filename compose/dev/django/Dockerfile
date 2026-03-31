# Dev Django image — uses pre-built base from ECR
ARG ECR_REGISTRY
FROM ${ECR_REGISTRY}/kcprofiles-base:latest

ARG APP_HOME=/app

ENV BUILD_ENV=dev

WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django django

COPY --chown=django:django ./compose/dev/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY --chown=django:django ./compose/dev/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

RUN chown -R django:django ${APP_HOME} /opt/venv

USER django

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
