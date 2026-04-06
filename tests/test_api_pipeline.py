"""Tests for POST /v1/pipeline/trigger."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FIXED_TIME, make_clinical_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_run(query_id: uuid.UUID, status: str = "completed") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.clinical_query_id = query_id
    run.status = status
    run.trigger_type = "api"
    run.started_at = FIXED_TIME
    run.completed_at = FIXED_TIME
    run.articles_found = 5
    run.articles_extracted = 3
    run.error_message = None
    run.meta = {"query_name": "SGLT2 Heart Failure"}
    return run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_trigger_success(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    mock_run = make_mock_run(sample_query.id)

    with patch("src.api.routes.pipeline.MonitorAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=mock_run)
        resp = await api_client.post(
            "/v1/pipeline/trigger",
            json={"query_id": str(sample_query.id)},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "completed"
    assert body["articles_found"] == 5
    assert body["articles_extracted"] == 3
    assert body["trigger_type"] == "api"


async def test_trigger_query_not_found(api_client, mock_db):
    mock_db.get.return_value = None
    resp = await api_client.post(
        "/v1/pipeline/trigger",
        json={"query_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_trigger_inactive_query_returns_422(api_client, mock_db, sample_query):
    inactive = make_clinical_query(is_active=False)
    mock_db.get.return_value = inactive
    resp = await api_client.post(
        "/v1/pipeline/trigger",
        json={"query_id": str(inactive.id)},
    )
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


async def test_trigger_passes_date_range_to_agent(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    mock_run = make_mock_run(sample_query.id)

    with patch("src.api.routes.pipeline.MonitorAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=mock_run)
        await api_client.post(
            "/v1/pipeline/trigger",
            json={
                "query_id": str(sample_query.id),
                "min_date": "2024/01/01",
                "max_date": "2024/12/31",
            },
        )
        _, call_kwargs = MockAgent.return_value.run.call_args
        assert call_kwargs.get("date_range") == ("2024/01/01", "2024/12/31")


async def test_trigger_no_date_range_passes_none(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    mock_run = make_mock_run(sample_query.id)

    with patch("src.api.routes.pipeline.MonitorAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=mock_run)
        await api_client.post(
            "/v1/pipeline/trigger",
            json={"query_id": str(sample_query.id)},
        )
        _, call_kwargs = MockAgent.return_value.run.call_args
        assert call_kwargs.get("date_range") is None


async def test_trigger_passes_trigger_type(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    mock_run = make_mock_run(sample_query.id)
    mock_run.trigger_type = "manual"

    with patch("src.api.routes.pipeline.MonitorAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=mock_run)
        await api_client.post(
            "/v1/pipeline/trigger",
            json={"query_id": str(sample_query.id), "trigger_type": "manual"},
        )
        _, call_kwargs = MockAgent.return_value.run.call_args
        assert call_kwargs.get("trigger_type") == "manual"


async def test_trigger_invalid_trigger_type_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/pipeline/trigger",
        json={"query_id": str(uuid.uuid4()), "trigger_type": "unknown"},
    )
    assert resp.status_code == 422


async def test_trigger_max_results_respected(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    mock_run = make_mock_run(sample_query.id)

    with patch("src.api.routes.pipeline.MonitorAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=mock_run)
        await api_client.post(
            "/v1/pipeline/trigger",
            json={"query_id": str(sample_query.id), "max_results": 250},
        )
        _, call_kwargs = MockAgent.return_value.run.call_args
        assert call_kwargs.get("max_results") == 250


async def test_trigger_missing_query_id_returns_422(api_client, mock_db):
    resp = await api_client.post("/v1/pipeline/trigger", json={})
    assert resp.status_code == 422


async def test_trigger_invalid_date_format_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/pipeline/trigger",
        json={
            "query_id": str(uuid.uuid4()),
            "min_date": "2024-01-01",  # wrong format (dashes instead of slashes)
        },
    )
    assert resp.status_code == 422
