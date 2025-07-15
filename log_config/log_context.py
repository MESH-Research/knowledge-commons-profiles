import contextvars
import logging
import os
import socket
import uuid

from django.conf import settings

_log_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "log_context", default=None
)


class ContextFilter(logging.Filter):
    def __init__(self, name=""):
        super().__init__(name)
        self.hostname = socket.gethostname()
        self.process_id = os.getpid()

    def filter(self, record):
        record.hostname = self.hostname
        record.process_id = self.process_id

        thread_local = settings.THREAD
        request = getattr(thread_local, "request", None)
        if request:
            request_id = getattr(request, "request_id", None)

            if not request_id:
                # Generate a new request_id if it doesn't exist or
                # get it from the headers
                request_id = request.headers.get(
                    "X-Request-ID", str(uuid.uuid4())
                )
                request.request_id = request_id

            # Set the request_id on the record
            record.request_id = request_id

        if _log_context.get() is None:
            _log_context.set({})

        context = _log_context.get()
        for key, value in context.items():
            setattr(record, key, value)

        return True
