"""FastAPI middleware: correlation ID propagation and Prometheus request metrics."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request.

    Reads ``X-Request-ID`` from incoming headers; generates a UUID4 if absent.
    Binds the ID to structlog context-vars so every log line emitted during the
    request automatically includes ``correlation_id``.  Sets the same value on
    the response header so callers can trace requests end-to-end.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = correlation_id
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request latency for every route.

    Uses ``api_request_latency_seconds`` histogram from ``src.core.metrics``.
    Path parameters are normalised to avoid label cardinality explosion
    (e.g. ``/v1/queries/abc-123`` → ``/v1/queries/{id}``).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Import lazily to avoid circular import at module load time
        from src.core.metrics import api_request_latency_seconds

        path = _normalise_path(request.url.path)
        api_request_latency_seconds.labels(
            method=request.method,
            endpoint=path,
            status_code=str(response.status_code),
        ).observe(duration)

        return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATH_PARAM_PATTERN = None


def _normalise_path(path: str) -> str:
    """Replace UUID/integer segments with ``{id}`` to reduce label cardinality."""
    import re

    global _PATH_PARAM_PATTERN
    if _PATH_PARAM_PATTERN is None:
        _PATH_PARAM_PATTERN = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|(?<=/)\d+",
            re.IGNORECASE,
        )
    return _PATH_PARAM_PATTERN.sub("{id}", path)
