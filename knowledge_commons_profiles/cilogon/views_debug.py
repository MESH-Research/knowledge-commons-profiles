"""
DEBUG-only diagnostic views for the broker flow.

These endpoints are gated by ``settings.DEBUG`` and exist purely so we
can quantify the broker hot paths without depending on production
traffic. They MUST NOT be registered when ``DEBUG`` is false — both the
URL conf and each view double-check this.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict

from django.conf import settings
from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.test import Client
from django.views.decorators.http import require_http_methods

MAX_ITERATIONS = 500
DEFAULT_ITERATIONS = 20
DEFAULT_RETURN_TO = "https://hcommons.org/broker-callback/"


@require_http_methods(["GET"])
def broker_timings_debug(request):
    """
    Run ``n`` synthetic in-process calls against ``/broker/silent-login/``
    and return per-span percentiles parsed from the response's
    ``Server-Timing`` header.

    Intended for local profiling under a debugger or `ab`/`hey`-style
    load shaping. Anonymous-only (no_session branch) by default — pass
    ``?authenticated=1`` to authenticate a synthetic test user instead.
    """
    if not settings.DEBUG:
        # Plain 404 (no template render) so the endpoint stays inert
        # even if it's accidentally exposed in production.
        return HttpResponseNotFound("not found")

    try:
        n = int(request.GET.get("n", str(DEFAULT_ITERATIONS)))
    except (TypeError, ValueError):
        n = DEFAULT_ITERATIONS
    n = max(1, min(n, MAX_ITERATIONS))

    return_to = request.GET.get("return_to", DEFAULT_RETURN_TO)
    final_redirect = request.GET.get("final_redirect", "")

    # Use a non-INTERNAL_IPS REMOTE_ADDR so Django Debug Toolbar's
    # SHOW_TOOLBAR_CALLBACK returns False for these synthetic requests;
    # otherwise the toolbar tries to render itself on every inner
    # response and skews the timings (and can blow up in tests).
    client = Client(REMOTE_ADDR="203.0.113.1")
    totals_ms: list[float] = []
    spans_by_name: dict[str, list[float]] = defaultdict(list)

    params = {"return_to": return_to}
    if final_redirect:
        params["final_redirect"] = final_redirect

    for _ in range(n):
        start = time.perf_counter()
        response = client.get("/broker/silent-login/", data=params)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        totals_ms.append(elapsed_ms)

        header = response.get("Server-Timing", "")
        for raw_entry in header.split(","):
            entry = raw_entry.strip()
            if not entry or ";dur=" not in entry:
                continue
            name, _, dur = entry.partition(";dur=")
            try:
                spans_by_name[name.strip()].append(float(dur.strip()))
            except ValueError:
                continue

    return JsonResponse(
        {
            "n": n,
            "return_to": return_to,
            "totals_ms": _stats(totals_ms),
            "spans_ms": {
                name: _stats(values)
                for name, values in spans_by_name.items()
            },
        }
    )


def _stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": ordered[0],
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def _percentile(ordered: list[float], pct: int) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    # Nearest-rank percentile; cheap and deterministic.
    last = len(ordered) - 1
    k = max(0, min(last, int(round(pct / 100 * last))))
    return ordered[k]
