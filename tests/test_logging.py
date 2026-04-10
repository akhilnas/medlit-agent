"""Tests for structured logging configuration and correlation ID middleware."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import structlog

from src.api.middleware import CorrelationIdMiddleware, _normalise_path


# ---------------------------------------------------------------------------
# Logging configuration tests
# ---------------------------------------------------------------------------


def test_configure_logging_sets_structlog_processors():
    """configure_logging() should configure structlog without raising."""
    from src.core.logging import configure_logging

    # Should not raise
    configure_logging()
    config = structlog.get_config()
    assert config["logger_factory"] is not None
    assert config["wrapper_class"] is structlog.stdlib.BoundLogger


def test_get_logger_returns_bound_logger():
    """get_logger() should return a usable structlog BoundLogger."""
    from src.core.logging import configure_logging, get_logger

    configure_logging()
    logger = get_logger("test_module")
    # Should not raise when logging
    logger.info("test event", key="value")


# ---------------------------------------------------------------------------
# CorrelationIdMiddleware tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correlation_id_middleware_generates_id_when_absent():
    """Middleware should generate a UUID correlation ID when header is absent."""
    middleware = CorrelationIdMiddleware(app=MagicMock())

    mock_response = MagicMock()
    mock_response.headers = {}

    async def call_next(request):
        return mock_response

    request = MagicMock()
    request.headers = {}
    request.headers.get = lambda key, default=None: None

    response = await middleware.dispatch(request, call_next)
    assert "X-Request-ID" in response.headers
    rid = response.headers["X-Request-ID"]
    # Should be a valid UUID4
    import uuid
    uuid.UUID(rid)  # raises if invalid


@pytest.mark.asyncio
async def test_correlation_id_middleware_uses_existing_header():
    """Middleware should echo back an existing X-Request-ID header."""
    middleware = CorrelationIdMiddleware(app=MagicMock())

    existing_id = "test-request-id-12345"
    mock_response = MagicMock()
    mock_response.headers = {}

    async def call_next(request):
        return mock_response

    request = MagicMock()
    request.headers.get = lambda key, default=None: (
        existing_id if key == "X-Request-ID" else default
    )

    response = await middleware.dispatch(request, call_next)
    assert response.headers["X-Request-ID"] == existing_id


@pytest.mark.asyncio
async def test_correlation_id_middleware_clears_context_after_request():
    """Context vars should be cleared after each request to prevent leakage."""
    middleware = CorrelationIdMiddleware(app=MagicMock())

    # Bind something before the request
    structlog.contextvars.bind_contextvars(pre_existing="value")

    mock_response = MagicMock()
    mock_response.headers = {}

    async def call_next(request):
        return mock_response

    request = MagicMock()
    request.headers.get = lambda key, default=None: None

    await middleware.dispatch(request, call_next)

    # After the request, context vars should be cleared
    ctx = structlog.contextvars.get_contextvars()
    assert ctx == {}


# ---------------------------------------------------------------------------
# Path normalisation tests
# ---------------------------------------------------------------------------


def test_normalise_path_replaces_uuid():
    path = "/v1/queries/550e8400-e29b-41d4-a716-446655440000"
    assert _normalise_path(path) == "/v1/queries/{id}"


def test_normalise_path_replaces_integer_segment():
    path = "/v1/articles/42/details"
    assert _normalise_path(path) == "/v1/articles/{id}/details"


def test_normalise_path_leaves_non_id_segments_unchanged():
    path = "/v1/pipeline/trigger"
    assert _normalise_path(path) == "/v1/pipeline/trigger"


def test_normalise_path_metrics_endpoint():
    path = "/metrics"
    assert _normalise_path(path) == "/metrics"
