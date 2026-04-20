import logging


class HealthCheckFilter(logging.Filter):
    """Filter out error log records originating from health check requests.

    Intended for use on Django's mail_admins handler so that expected
    infrastructure failures reported by the /health/ endpoint do not
    generate admin notification emails.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        request = getattr(record, "request", None)
        if request is not None:
            path = getattr(request, "path", "")
            if path.rstrip("/") == "/health":
                return False
        return True
