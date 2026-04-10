"""Tests for src/agents/embedder.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.embedder import EmbeddingAgent, _batched
from src.models.article_embedding import ArticleEmbedding
from src.services.embedding_service import EmbeddingInput, EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article(pmid: str = "12345", status: str = "extracted") -> MagicMock:
    a = MagicMock()
    a.id = uuid.uuid4()
    a.pmid = pmid
    a.title = f"Article {pmid}"
    a.abstract = "Abstract text."
    a.clinical_query_id = uuid.uuid4()
    a.processing_status = status
    return a


def make_mock_svc(dim: int = 768) -> MagicMock:
    """EmbeddingService mock with pre-built inputs and embed_texts."""
    svc = MagicMock(spec=EmbeddingService)
    svc._model_name = "NeuML/pubmedbert-base-embeddings"
    svc.build_inputs = MagicMock(
        return_value=[EmbeddingInput(embedding_type="abstract", text="some text")]
    )
    svc.embed_texts = AsyncMock(return_value=[[0.1] * dim])
    return svc


def make_mock_db(articles: list | None = None) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()

    # _fetch_pending query
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = articles or []

    # _load_picos query
    pico_result = MagicMock()
    pico_result.scalars.return_value.all.return_value = []

    db.execute.side_effect = [fetch_result, pico_result]
    return db


# ---------------------------------------------------------------------------
# _batched utility
# ---------------------------------------------------------------------------

def test_batched_splits_correctly():
    items = list(range(7))
    batches = list(_batched(items, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6]]


def test_batched_empty():
    assert list(_batched([], 5)) == []


def test_batched_exact_size():
    assert list(_batched([1, 2, 3], 3)) == [[1, 2, 3]]


# ---------------------------------------------------------------------------
# EmbeddingAgent.run()
# ---------------------------------------------------------------------------

async def test_run_embeds_article_successfully():
    article = make_article()
    svc = make_mock_svc()
    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    # Disable re-scoring to keep mock simple
    agent._update_relevance_scores = AsyncMock()

    stats = await agent.run()

    assert stats["embedded"] == 1
    assert stats["failed"] == 0
    assert stats["skipped"] == 0
    db.add.assert_called_once()
    db.commit.assert_called()


async def test_run_skips_article_with_no_text():
    article = make_article()
    svc = make_mock_svc()
    svc.build_inputs = MagicMock(return_value=[])  # no inputs

    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    stats = await agent.run()

    assert stats["skipped"] == 1
    assert stats["embedded"] == 0
    svc.embed_texts.assert_not_called()


async def test_run_does_not_mark_failed_on_embed_error():
    """Embed errors leave article as 'extracted' for retry — not permanently failed."""
    article = make_article()
    svc = make_mock_svc()
    svc.embed_texts = AsyncMock(side_effect=RuntimeError("GPU OOM"))

    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    stats = await agent.run()

    assert stats["failed"] == 1
    # Article status must NOT be changed to "failed"
    assert article.processing_status == "extracted"


async def test_run_empty_pending_returns_zeros():
    svc = make_mock_svc()
    db = make_mock_db([])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    stats = await agent.run()

    assert stats == {"embedded": 0, "failed": 0, "skipped": 0}
    svc.embed_texts.assert_not_called()


async def test_run_creates_embedding_record_with_correct_type():
    article = make_article()
    svc = make_mock_svc()
    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    await agent.run()

    added = db.add.call_args[0][0]
    assert isinstance(added, ArticleEmbedding)
    assert added.embedding_type == "abstract"
    assert added.article_id == article.id
    assert added.model_name == svc._model_name


async def test_run_produces_both_abstract_and_pico_embeddings():
    article = make_article()
    svc = make_mock_svc()
    svc.build_inputs = MagicMock(return_value=[
        EmbeddingInput(embedding_type="abstract", text="title abstract"),
        EmbeddingInput(embedding_type="pico", text="population intervention"),
    ])
    svc.embed_texts = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])

    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    await agent.run()

    assert db.add.call_count == 2
    types = {db.add.call_args_list[i][0][0].embedding_type for i in range(2)}
    assert types == {"abstract", "pico"}


async def test_run_respects_limit():
    svc = make_mock_svc()
    db = make_mock_db([])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    await agent.run(limit=5)

    db.execute.assert_called()  # fetch query was issued


async def test_run_uses_injected_service():
    svc = make_mock_svc()
    db = make_mock_db([])

    with patch("src.agents.embedder.EmbeddingService") as MockSvc:
        agent = EmbeddingAgent(db, embedding_service=svc)
        agent._update_relevance_scores = AsyncMock()
        await agent.run()
        MockSvc.assert_not_called()


async def test_run_calls_update_relevance_after_embedding():
    article = make_article()
    svc = make_mock_svc()
    db = make_mock_db([article])

    agent = EmbeddingAgent(db, embedding_service=svc)
    agent._update_relevance_scores = AsyncMock()

    await agent.run()

    agent._update_relevance_scores.assert_called_once()
