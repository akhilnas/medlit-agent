"""Tests for POST /v1/articles/search."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FIXED_TIME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_search_row(
    pmid: str = "12345",
    similarity_score: float = 0.85,
    vector_score: float = 0.90,
    fts_score: float = 0.60,
) -> MagicMock:
    row = MagicMock()
    row.article_id = uuid.uuid4()
    row.pmid = pmid
    row.title = f"Article {pmid}"
    row.journal = "NEJM"
    row.publication_date = date(2024, 3, 15)
    row.relevance_score = 0.9
    row.similarity_score = similarity_score
    row.vector_score = vector_score
    row.fts_score = fts_score
    row.study_design = "randomized_controlled_trial"
    row.evidence_level = "II"
    return row


def _db_with_search_rows(mock_db, rows: list) -> None:
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(rows))
    mock_db.execute.return_value = result


MOCK_VECTOR = [0.1] * 768


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_search_success(api_client, mock_db):
    rows = [make_search_row(pmid=str(i)) for i in range(3)]
    _db_with_search_rows(mock_db, rows)

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "SGLT2 heart failure"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "SGLT2 heart failure"
    assert body["embedding_type"] == "abstract"
    assert body["total"] == 3
    assert len(body["results"]) == 3


async def test_search_returns_similarity_scores(api_client, mock_db):
    rows = [make_search_row(similarity_score=0.87, vector_score=0.91, fts_score=0.70)]
    _db_with_search_rows(mock_db, rows)

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "SGLT2 heart failure"},
        )

    result = resp.json()["results"][0]
    assert result["similarity_score"] == pytest.approx(0.87)
    assert result["vector_score"] == pytest.approx(0.91)
    assert result["fts_score"] == pytest.approx(0.70)


async def test_search_empty_results(api_client, mock_db):
    _db_with_search_rows(mock_db, [])

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "very obscure query"},
        )

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["results"] == []


async def test_search_query_too_short_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/articles/search",
        json={"query": "ab"},  # min_length=3
    )
    assert resp.status_code == 422


async def test_search_limit_out_of_range_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/articles/search",
        json={"query": "SGLT2", "limit": 999},  # max=50
    )
    assert resp.status_code == 422


async def test_search_min_similarity_out_of_range_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/articles/search",
        json={"query": "SGLT2", "min_similarity": 1.5},
    )
    assert resp.status_code == 422


async def test_search_pico_embedding_type(api_client, mock_db):
    _db_with_search_rows(mock_db, [])

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "SGLT2 heart failure", "embedding_type": "pico"},
        )

    assert resp.status_code == 200
    assert resp.json()["embedding_type"] == "pico"


async def test_search_invalid_embedding_type_rejected(api_client, mock_db):
    resp = await api_client.post(
        "/v1/articles/search",
        json={"query": "SGLT2", "embedding_type": "invalid"},
    )
    assert resp.status_code == 422


async def test_search_with_study_design_filter(api_client, mock_db):
    rows = [make_search_row()]
    _db_with_search_rows(mock_db, rows)

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={
                "query": "SGLT2 heart failure",
                "study_design": "randomized_controlled_trial",
            },
        )

    assert resp.status_code == 200


async def test_search_with_date_filters(api_client, mock_db):
    rows = [make_search_row()]
    _db_with_search_rows(mock_db, rows)

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={
                "query": "SGLT2 heart failure",
                "date_from": "2023-01-01",
                "date_to": "2024-12-31",
            },
        )

    assert resp.status_code == 200


async def test_search_returns_503_when_embedding_fails(api_client, mock_db):
    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(
            side_effect=RuntimeError("model not loaded")
        )
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "SGLT2 heart failure"},
        )

    assert resp.status_code == 503


async def test_search_result_includes_pico_fields(api_client, mock_db):
    row = make_search_row()
    _db_with_search_rows(mock_db, [row])

    with patch("src.api.routes.articles.EmbeddingService") as MockSvc:
        MockSvc.return_value.embed_texts = AsyncMock(return_value=[MOCK_VECTOR])
        resp = await api_client.post(
            "/v1/articles/search",
            json={"query": "SGLT2 heart failure"},
        )

    result = resp.json()["results"][0]
    assert result["study_design"] == "randomized_controlled_trial"
    assert result["evidence_level"] == "II"
