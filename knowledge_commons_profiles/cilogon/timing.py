"""
Lightweight per-request timing collector for the broker views.

Each instrumented view builds a :class:`TimingCollector`, records named
spans around the work it does, and emits them as a ``Server-Timing``
response header when ``settings.BROKER_TIMING_ENABLED`` is true. Browsers
expose Server-Timing in DevTools; ``curl -I`` shows it too, so the same
header drives both interactive debugging and the in-process synthetic
profiler in :mod:`knowledge_commons_profiles.cilogon.views_debug`.

The collector is deliberately tiny — no thread-locals, no global state —
so it stays cheap on the hot path and trivially safe under load.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from django.conf import settings

_HEADER_NAME = "Server-Timing"


class TimingCollector:
    """Records ordered (name, duration_ms) spans for a single request."""

    __slots__ = ("spans",)

    def __init__(self) -> None:
        self.spans: list[tuple[str, float]] = []

    @contextmanager
    def span(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.spans.append(
                (name, (time.perf_counter() - start) * 1000.0)
            )

    def header_value(self) -> str:
        """Format spans as a Server-Timing header value."""
        return ", ".join(
            f"{name};dur={ms:.2f}" for name, ms in self.spans
        )

    def as_dict(self) -> dict[str, float]:
        """Flatten spans into a name -> milliseconds dict.

        If the same span name appears twice in a single request, the
        last value wins. Use :attr:`spans` directly when ordering
        matters.
        """
        return dict(self.spans)


def is_enabled() -> bool:
    """Whether Server-Timing headers should be emitted."""
    return bool(getattr(settings, "BROKER_TIMING_ENABLED", False))


def apply_header(response, collector: TimingCollector) -> None:
    """Attach the Server-Timing header to ``response`` if enabled."""
    if not is_enabled():
        return
    value = collector.header_value()
    if value:
        response[_HEADER_NAME] = value
