"""Prometheus metric singletons for the MedLit Agent.

All metrics are declared at **module level** so they are created exactly once
per Python process.  This prevents ``ValueError: Duplicated timeseries`` errors
when uvicorn's ``--reload`` re-imports modules during development.

Usage::

    from src.core.metrics import articles_processed_total, pipeline_duration_seconds

    articles_processed_total.labels(status="found").inc(10)

    with pipeline_duration_seconds.labels(phase="monitor", query_id=str(qid)).time():
        await monitor_agent.run(...)
"""

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

pipeline_duration_seconds = Histogram(
    "pipeline_duration_seconds",
    "Time spent in each pipeline phase",
    labelnames=["phase", "query_id"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

articles_processed_total = Counter(
    "articles_processed_total",
    "Cumulative count of articles processed, by outcome",
    labelnames=["status"],  # found | extracted | embedded | failed
)

# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------

llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Cumulative LLM token usage",
    labelnames=["model", "direction"],  # direction: input | output
)

# ---------------------------------------------------------------------------
# Embedding metrics
# ---------------------------------------------------------------------------

embedding_generation_seconds = Histogram(
    "embedding_generation_seconds",
    "Time spent generating embeddings for a batch of articles",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
)

# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

api_request_latency_seconds = Histogram(
    "api_request_latency_seconds",
    "HTTP request latency",
    labelnames=["method", "endpoint", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
