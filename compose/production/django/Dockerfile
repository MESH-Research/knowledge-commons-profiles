# Production Django image — uses pre-built base from ECR
ARG ECR_REGISTRY
FROM ${ECR_REGISTRY}/kcprofiles-base:latest

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django django

COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

RUN chown -R django:django ${APP_HOME}

USER django

ENTRYPOINT ["/entrypoint"]
CMD ["/start"]
