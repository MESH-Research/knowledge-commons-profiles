import traceback

import pythonjsonlogger


class StructuredExceptionJsonFormatter(pythonjsonlogger.json.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            log_record["exception"] = {
                "exc_type": exc_type.__name__,
                "exc_value": str(exc_value),
                "traceback": traceback.format_exception(
                    exc_type, exc_value, exc_traceback
                ),
            }

            log_record.pop("exc_info", None)
            log_record.pop("exc_text", None)
