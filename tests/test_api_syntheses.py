"""Tests for GET /v1/syntheses and GET /v1/syntheses/{id}."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from tests.conftest import FIXED_TIME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_synthesis(
    query_id: uuid.UUID | None = None,
    evidence_grade: str = "A",
    consensus_status: str = "consistent",
) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.clinical_query_id = query_id or uuid.uuid4()
    s.pipeline_run_id = None
    s.summary_text = "SGLT2i significantly reduce hospitalizations in HF."
    s.evidence_grade = evidence_grade
    s.consensus_status = consensus_status
    s.key_findings = ["Reduced HHF by 25%"]
    s.evidence_gaps = ["Long-term safety data lacking"]
    s.article_count = 5
    s.synthesis_model = "claude-sonnet-4-6"
    s.created_at = FIXED_TIME
    return s


def _db_with_syntheses(mock_db, syntheses: list, total: int | None = None) -> None:
    count_result = MagicMock()
    count_result.scalar_one.return_value = total if total is not None else len(syntheses)

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = syntheses

    mock_db.execute.side_effect = [count_result, list_result]


def _db_with_single(mock_db, synthesis) -> None:
    mock_db.get.return_value = synthesis


# ---------------------------------------------------------------------------
# GET /v1/syntheses
# ---------------------------------------------------------------------------

async def test_list_syntheses_empty(api_client, mock_db):
    _db_with_syntheses(mock_db, [], total=0)
    resp = await api_client.get("/v1/syntheses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["data"] == []


async def test_list_syntheses_returns_items(api_client, mock_db):
    syntheses = [make_synthesis() for _ in range(3)]
    _db_with_syntheses(mock_db, syntheses)
    resp = await api_client.get("/v1/syntheses")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
    assert len(resp.json()["data"]) == 3


async def test_list_syntheses_includes_summary(api_client, mock_db):
    s = make_synthesis()
    _db_with_syntheses(mock_db, [s])
    resp = await api_client.get("/v1/syntheses")
    item = resp.json()["data"][0]
    assert "SGLT2i" in item["summary_text"]
    assert item["evidence_grade"] == "A"
    assert item["consensus_status"] == "consistent"


async def test_list_syntheses_filter_by_query_id(api_client, mock_db):
    qid = uuid.uuid4()
    s = make_synthesis(query_id=qid)
    _db_with_syntheses(mock_db, [s])
    resp = await api_client.get(f"/v1/syntheses?query_id={qid}")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["clinical_query_id"] == str(qid)


async def test_list_syntheses_pagination(api_client, mock_db):
    _db_with_syntheses(mock_db, [], total=50)
    resp = await api_client.get("/v1/syntheses?limit=10&offset=20")
    assert resp.status_code == 200
    assert resp.json()["total"] == 50


# ---------------------------------------------------------------------------
# GET /v1/syntheses/{id}
# ---------------------------------------------------------------------------

async def test_get_synthesis_success(api_client, mock_db):
    s = make_synthesis()
    _db_with_single(mock_db, s)
    resp = await api_client.get(f"/v1/syntheses/{s.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(s.id)


async def test_get_synthesis_not_found(api_client, mock_db):
    mock_db.get.return_value = None
    resp = await api_client.get(f"/v1/syntheses/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_synthesis_includes_key_findings(api_client, mock_db):
    s = make_synthesis()
    _db_with_single(mock_db, s)
    resp = await api_client.get(f"/v1/syntheses/{s.id}")
    body = resp.json()
    assert isinstance(body["key_findings"], list)
    assert isinstance(body["evidence_gaps"], list)
