"""Tests for GET/POST/PATCH/DELETE /v1/queries endpoints."""

import uuid
from unittest.mock import AsyncMock

import pytest

from tests.conftest import FIXED_TIME, make_clinical_query, rows_result, scalar_result


# ---------------------------------------------------------------------------
# GET /v1/queries
# ---------------------------------------------------------------------------

async def test_list_queries_empty(api_client, mock_db):
    mock_db.execute.side_effect = [scalar_result(0), rows_result([])]
    resp = await api_client.get("/v1/queries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


async def test_list_queries_returns_items(api_client, mock_db, sample_query):
    mock_db.execute.side_effect = [scalar_result(1), rows_result([sample_query])]
    resp = await api_client.get("/v1/queries")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == sample_query.name
    assert body["pagination"]["total"] == 1


async def test_list_queries_filter_active(api_client, mock_db, sample_query):
    mock_db.execute.side_effect = [scalar_result(1), rows_result([sample_query])]
    resp = await api_client.get("/v1/queries?is_active=true")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


async def test_list_queries_filter_inactive_returns_empty(api_client, mock_db):
    mock_db.execute.side_effect = [scalar_result(0), rows_result([])]
    resp = await api_client.get("/v1/queries?is_active=false")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 0


async def test_list_queries_pagination_reflected_in_response(api_client, mock_db):
    mock_db.execute.side_effect = [scalar_result(42), rows_result([])]
    resp = await api_client.get("/v1/queries?page=3&per_page=10")
    assert resp.status_code == 200
    pagination = resp.json()["pagination"]
    assert pagination["page"] == 3
    assert pagination["per_page"] == 10
    assert pagination["total"] == 42


async def test_list_queries_invalid_page_rejected(api_client, mock_db):
    resp = await api_client.get("/v1/queries?page=0")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/queries
# ---------------------------------------------------------------------------

VALID_CREATE_BODY = {
    "name": "GLP-1 NASH Study",
    "description": "GLP-1 agonists in NASH",
    "pubmed_query": "GLP-1 AND NASH",
    "mesh_terms": ["Non-alcoholic Fatty Liver Disease"],
    "min_relevance_score": 0.75,
    "is_active": True,
    "schedule_cron": "0 6 * * 1",
}


async def test_create_query_returns_201(api_client, mock_db):
    resp = await api_client.post("/v1/queries", json=VALID_CREATE_BODY)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "GLP-1 NASH Study"
    assert body["pubmed_query"] == "GLP-1 AND NASH"
    assert "id" in body


async def test_create_query_commits_to_db(api_client, mock_db):
    await api_client.post("/v1/queries", json=VALID_CREATE_BODY)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_create_query_missing_required_field(api_client, mock_db):
    body = {k: v for k, v in VALID_CREATE_BODY.items() if k != "pubmed_query"}
    resp = await api_client.post("/v1/queries", json=body)
    assert resp.status_code == 422


async def test_create_query_score_out_of_range(api_client, mock_db):
    body = {**VALID_CREATE_BODY, "min_relevance_score": 1.5}
    resp = await api_client.post("/v1/queries", json=body)
    assert resp.status_code == 422


async def test_create_query_defaults_applied(api_client, mock_db):
    minimal = {"name": "Minimal Query", "pubmed_query": "minimal"}
    resp = await api_client.post("/v1/queries", json=minimal)
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_active"] is True
    assert body["min_relevance_score"] == 0.7


# ---------------------------------------------------------------------------
# GET /v1/queries/{id}
# ---------------------------------------------------------------------------

async def test_get_query_returns_200(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    resp = await api_client.get(f"/v1/queries/{sample_query.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sample_query.id)


async def test_get_query_not_found(api_client, mock_db):
    mock_db.get.return_value = None
    resp = await api_client.get(f"/v1/queries/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PATCH /v1/queries/{id}
# ---------------------------------------------------------------------------

async def test_update_query_returns_updated_fields(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    resp = await api_client.patch(
        f"/v1/queries/{sample_query.id}",
        json={"name": "Updated Name", "is_active": False},
    )
    assert resp.status_code == 200
    # The fixture object was mutated in-place by setattr
    assert sample_query.name == "Updated Name"
    assert sample_query.is_active is False


async def test_update_query_partial_update_only_touches_sent_fields(api_client, mock_db, sample_query):
    original_pubmed_query = sample_query.pubmed_query
    mock_db.get.return_value = sample_query
    await api_client.patch(f"/v1/queries/{sample_query.id}", json={"name": "New Name"})
    assert sample_query.pubmed_query == original_pubmed_query  # untouched


async def test_update_query_not_found(api_client, mock_db):
    mock_db.get.return_value = None
    resp = await api_client.patch(f"/v1/queries/{uuid.uuid4()}", json={"name": "X"})
    assert resp.status_code == 404


async def test_update_query_invalid_score(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    resp = await api_client.patch(
        f"/v1/queries/{sample_query.id}",
        json={"min_relevance_score": -0.1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /v1/queries/{id}
# ---------------------------------------------------------------------------

async def test_delete_query_returns_204(api_client, mock_db, sample_query):
    mock_db.get.return_value = sample_query
    resp = await api_client.delete(f"/v1/queries/{sample_query.id}")
    assert resp.status_code == 204
    mock_db.delete.assert_called_once_with(sample_query)
    mock_db.commit.assert_called_once()


async def test_delete_query_not_found(api_client, mock_db):
    mock_db.get.return_value = None
    resp = await api_client.delete(f"/v1/queries/{uuid.uuid4()}")
    assert resp.status_code == 404
