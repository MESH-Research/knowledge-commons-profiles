from debug_toolbar.panels import Panel
from django.db import connection


class QueryTimingPanel(Panel):
    """
    Simple panel showing only query count
    """

    title = "SQL Count"

    def nav_subtitle(self):
        return f"{len(connection.queries)} queries"

    def enable_instrumentation(self):
        pass

    def disable_instrumentation(self):
        pass
