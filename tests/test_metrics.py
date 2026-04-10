"""Tests for Prometheus metrics module and /metrics endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.core.metrics import (
    api_request_latency_seconds,
    articles_processed_total,
    embedding_generation_seconds,
    llm_tokens_used_total,
    pipeline_duration_seconds,
)


# ---------------------------------------------------------------------------
# Metric object tests
# ---------------------------------------------------------------------------


def test_metrics_module_exports_all_expected_metrics():
    """All five metric objects should be importable and have the right types."""
    from prometheus_client import Counter, Histogram

    assert isinstance(pipeline_duration_seconds, Histogram)
    assert isinstance(articles_processed_total, Counter)
    assert isinstance(llm_tokens_used_total, Counter)
    assert isinstance(embedding_generation_seconds, Histogram)
    assert isinstance(api_request_latency_seconds, Histogram)


def test_articles_processed_total_labels():
    """articles_processed_total should accept expected status labels."""
    for status in ("found", "extracted", "embedded", "failed"):
        # Should not raise
        articles_processed_total.labels(status=status).inc(0)


def test_llm_tokens_used_total_labels():
    """llm_tokens_used_total should accept model and direction labels."""
    llm_tokens_used_total.labels(model="gemini-2.5-flash", direction="input").inc(0)
    llm_tokens_used_total.labels(model="gemini-2.5-flash", direction="output").inc(0)


def test_pipeline_duration_seconds_labels():
    """pipeline_duration_seconds should accept phase and query_id labels."""
    import uuid
    qid = str(uuid.uuid4())
    for phase in ("monitor", "extract", "embed", "synthesize"):
        pipeline_duration_seconds.labels(phase=phase, query_id=qid).observe(0.1)


def test_api_request_latency_seconds_labels():
    """api_request_latency_seconds should accept method, endpoint, status_code labels."""
    api_request_latency_seconds.labels(
        method="GET", endpoint="/v1/articles", status_code="200"
    ).observe(0.05)


# ---------------------------------------------------------------------------
# /metrics endpoint test
# ---------------------------------------------------------------------------


def test_metrics_endpoint_returns_prometheus_format(api_client):
    """GET /metrics should return 200 with Prometheus text exposition format."""
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Should contain at least our custom metric names
    body = response.text
    assert "api_request_latency_seconds" in body


def test_metrics_endpoint_not_in_openapi_schema(api_client):
    """GET /metrics should be excluded from the OpenAPI docs."""
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/metrics" not in paths


# ---------------------------------------------------------------------------
# LLM token counter instrumentation test
# ---------------------------------------------------------------------------


def test_gemini_client_increments_token_counter():
    """GeminiClient.complete() should increment llm_tokens_used_total on success."""
    import asyncio

    from src.services.gemini_client import GeminiClient, TokenUsage

    client = GeminiClient.__new__(GeminiClient)
    client._model = "gemini-2.5-flash"
    client._max_retries = 0
    client.usage = TokenUsage()

    mock_response = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 100
    mock_response.usage_metadata.candidates_token_count = 50
    mock_response.text = '{"result": "ok"}'

    mock_genai_client = MagicMock()
    mock_genai_client.aio.models.generate_content = AsyncMock(
        return_value=mock_response
    )
    client._client = mock_genai_client

    # Record current counter value before the call
    before_input = llm_tokens_used_total.labels(
        model="gemini-2.5-flash", direction="input"
    )._value.get()
    before_output = llm_tokens_used_total.labels(
        model="gemini-2.5-flash", direction="output"
    )._value.get()

    asyncio.get_event_loop().run_until_complete(
        client.complete(system="sys", user="user")
    )

    after_input = llm_tokens_used_total.labels(
        model="gemini-2.5-flash", direction="input"
    )._value.get()
    after_output = llm_tokens_used_total.labels(
        model="gemini-2.5-flash", direction="output"
    )._value.get()

    assert after_input - before_input == 100
    assert after_output - before_output == 50
