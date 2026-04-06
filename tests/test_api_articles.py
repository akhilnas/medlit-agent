"""Tests for GET /v1/articles."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import FIXED_TIME, scalar_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_pico(article_id: uuid.UUID | None = None) -> MagicMock:
    pico = MagicMock()
    pico.id = uuid.uuid4()
    pico.article_id = article_id or uuid.uuid4()
    pico.population = "Adults with HF"
    pico.intervention = "Empagliflozin"
    pico.comparison = "Placebo"
    pico.outcome = "CV death or HF hospitalisation"
    pico.study_design = "randomized_controlled_trial"
    pico.sample_size = 3730
    pico.effect_size = "HR=0.75"
    pico.confidence_interval = "95% CI 0.65-0.86"
    pico.p_value = "p<0.001"
    pico.evidence_level = "II"
    pico.extraction_model = "claude-sonnet-4-6"
    pico.extraction_confidence = 0.95
    pico.extracted_at = FIXED_TIME
    return pico


def make_mock_article(
    pmid: str = "12345",
    processing_status: str = "extracted",
    with_pico: bool = True,
) -> MagicMock:
    article = MagicMock()
    article.id = uuid.uuid4()
    article.pmid = pmid
    article.title = f"Article {pmid}"
    article.abstract = "Abstract text."
    article.authors = [{"name": "John Smith", "affiliation": "MIT"}]
    article.journal = "NEJM"
    article.publication_date = date(2024, 3, 15)
    article.doi = "10.1234/test"
    article.mesh_headings = ["Heart Failure"]
    article.article_type = "Randomized Controlled Trial"
    article.clinical_query_id = uuid.uuid4()
    article.relevance_score = 0.9
    article.processing_status = processing_status
    article.fetched_at = FIXED_TIME
    article.created_at = FIXED_TIME
    article.pico_extraction = make_mock_pico(article.id) if with_pico else None
    return article


def _db_with_articles(mock_db, articles: list, total: int | None = None) -> None:
    """Configure mock_db.execute to return count then article rows."""
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = total if total is not None else len(articles)

    rows_mock = MagicMock()
    rows_mock.scalars.return_value.all.return_value = articles

    mock_db.execute.side_effect = [count_mock, rows_mock]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_list_articles_success(api_client, mock_db):
    articles = [make_mock_article(pmid=str(i)) for i in range(3)]
    _db_with_articles(mock_db, articles)

    resp = await api_client.get("/v1/articles")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["data"]) == 3
    assert body["limit"] == 50
    assert body["offset"] == 0


async def test_list_articles_includes_pico(api_client, mock_db):
    article = make_mock_article(with_pico=True)
    _db_with_articles(mock_db, [article])

    resp = await api_client.get("/v1/articles")

    assert resp.status_code == 200
    data = resp.json()["data"][0]
    assert data["pico_extraction"] is not None
    assert data["pico_extraction"]["study_design"] == "randomized_controlled_trial"
    assert data["pico_extraction"]["evidence_level"] == "II"


async def test_list_articles_null_pico(api_client, mock_db):
    article = make_mock_article(with_pico=False)
    _db_with_articles(mock_db, [article])

    resp = await api_client.get("/v1/articles")

    assert resp.status_code == 200
    assert resp.json()["data"][0]["pico_extraction"] is None


async def test_list_articles_empty(api_client, mock_db):
    _db_with_articles(mock_db, [], total=0)

    resp = await api_client.get("/v1/articles")

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["data"] == []


async def test_list_articles_filter_processing_status(api_client, mock_db):
    articles = [make_mock_article(processing_status="extracted")]
    _db_with_articles(mock_db, articles)

    resp = await api_client.get("/v1/articles?processing_status=extracted")

    assert resp.status_code == 200
    assert resp.json()["data"][0]["processing_status"] == "extracted"


async def test_list_articles_pagination(api_client, mock_db):
    articles = [make_mock_article(pmid=str(i)) for i in range(2)]
    _db_with_articles(mock_db, articles, total=10)

    resp = await api_client.get("/v1/articles?limit=2&offset=4")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert body["limit"] == 2
    assert body["offset"] == 4
    assert len(body["data"]) == 2


async def test_list_articles_limit_too_large_rejected(api_client, mock_db):
    resp = await api_client.get("/v1/articles?limit=9999")
    assert resp.status_code == 422


async def test_list_articles_negative_offset_rejected(api_client, mock_db):
    resp = await api_client.get("/v1/articles?offset=-1")
    assert resp.status_code == 422


async def test_list_articles_filter_study_design(api_client, mock_db):
    article = make_mock_article(with_pico=True)
    _db_with_articles(mock_db, [article])

    resp = await api_client.get("/v1/articles?study_design=randomized_controlled_trial")

    assert resp.status_code == 200
    # Just verify the request went through and returned data
    assert resp.json()["total"] == 1


async def test_list_articles_filter_evidence_level(api_client, mock_db):
    article = make_mock_article(with_pico=True)
    _db_with_articles(mock_db, [article])

    resp = await api_client.get("/v1/articles?evidence_level=II")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_list_articles_filter_clinical_query_id(api_client, mock_db):
    article = make_mock_article()
    _db_with_articles(mock_db, [article])
    qid = str(article.clinical_query_id)

    resp = await api_client.get(f"/v1/articles?clinical_query_id={qid}")

    assert resp.status_code == 200


async def test_list_articles_invalid_clinical_query_id(api_client, mock_db):
    resp = await api_client.get("/v1/articles?clinical_query_id=not-a-uuid")
    # UUID parsing raises ValueError → 500 or let it bubble; either way not 200
    assert resp.status_code != 200
