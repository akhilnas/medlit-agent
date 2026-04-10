"""Embedding Agent — Phase 3.

Fetches articles that have been extracted but not yet embedded, generates
PubMedBERT vectors for the abstract and PICO text, persists
:class:`~src.models.article_embedding.ArticleEmbedding` records, and
optionally re-scores ``articles.relevance_score`` via cosine similarity.

Two embedding types per article (stored as separate rows):
- ``abstract``  — title + abstract text
- ``pico``      — concatenated PICO fields (skipped when PICO is missing)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from itertools import islice

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.article import Article
from src.models.article_embedding import ArticleEmbedding
from src.models.clinical_query import ClinicalQuery
from src.models.pico_extraction import PicoExtraction
from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

_DEFAULT_CONCURRENCY = 4
_DEFAULT_BATCH_SIZE = 32


class EmbeddingAgent:
    """Generate and store PubMedBERT embeddings for extracted articles.

    Usage::

        async with AsyncSessionLocal() as db:
            agent = EmbeddingAgent(db)
            stats = await agent.run(limit=100)
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._db = db
        self._svc = embedding_service or EmbeddingService()
        self._sem = asyncio.Semaphore(concurrency)
        self._batch_size = batch_size

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, limit: int | None = None) -> dict:
        """Embed all pending articles (extracted, no embeddings yet).

        Args:
            limit: Maximum articles to process.  ``None`` means all.

        Returns:
            Dict with keys: ``embedded``, ``failed``, ``skipped``.
        """
        articles = await self._fetch_pending(limit)
        logger.info("EmbeddingAgent: %d articles to embed", len(articles))

        embedded = failed = skipped = 0

        for batch in _batched(articles, self._batch_size):
            b_embedded, b_failed, b_skipped = await self._process_batch(batch)
            embedded += b_embedded
            failed += b_failed
            skipped += b_skipped

        # Re-score relevance using embedding similarity
        if embedded:
            await self._update_relevance_scores(articles)

        logger.info(
            "EmbeddingAgent done | embedded=%d failed=%d skipped=%d",
            embedded, failed, skipped,
        )
        return {"embedded": embedded, "failed": failed, "skipped": skipped}

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    async def _process_batch(
        self, articles: list[Article]
    ) -> tuple[int, int, int]:
        """Embed one batch: load PICOs, collect texts, encode, insert."""
        # Eager-load PICO records for the batch in one query
        pico_map = await self._load_picos({a.id for a in articles})

        # Build all (article, EmbeddingInput) pairs
        all_inputs: list[tuple[Article, str, str]] = []  # (article, emb_type, text)
        skipped = 0

        for article in articles:
            pico = pico_map.get(article.id)
            inputs = self._svc.build_inputs(article, pico)
            if not inputs:
                logger.warning("No embeddable text for PMID=%s — skipped", article.pmid)
                skipped += 1
                continue
            for emb_input in inputs:
                all_inputs.append((article, emb_input.embedding_type, emb_input.text))

        if not all_inputs:
            return 0, 0, skipped

        texts = [t for _, _, t in all_inputs]

        try:
            async with self._sem:
                vectors = await self._svc.embed_texts(texts)
        except Exception as exc:
            logger.exception(
                "Embedding batch failed (%d texts): %s — will retry next run", len(texts), exc
            )
            # Do NOT mark as failed; leave as "extracted" so next run retries
            return 0, len(articles) - skipped, skipped

        now = datetime.now(timezone.utc)
        embedded_article_ids: set[uuid.UUID] = set()

        for (article, emb_type, _), vector in zip(all_inputs, vectors):
            record = ArticleEmbedding(
                id=uuid.uuid4(),
                article_id=article.id,
                embedding_type=emb_type,
                embedding=vector,
                model_name=self._svc._model_name,
                created_at=now,
            )
            self._db.add(record)
            embedded_article_ids.add(article.id)

        await self._db.commit()

        embedded = len(embedded_article_ids)
        logger.info("Batch: embedded %d articles (%d vectors)", embedded, len(all_inputs))
        return embedded, 0, skipped

    # ------------------------------------------------------------------
    # Relevance re-scoring
    # ------------------------------------------------------------------

    async def _update_relevance_scores(self, articles: list[Article]) -> None:
        """Re-score articles.relevance_score using cosine similarity.

        Groups articles by clinical_query_id, embeds each unique query
        text once, then updates all articles for that query in one SQL.
        """
        # Group article ids by query
        query_to_article_ids: dict[uuid.UUID, list[uuid.UUID]] = {}
        for article in articles:
            if article.clinical_query_id:
                query_to_article_ids.setdefault(article.clinical_query_id, []).append(article.id)

        if not query_to_article_ids:
            return

        for query_id, article_ids in query_to_article_ids.items():
            try:
                query = await self._db.get(ClinicalQuery, query_id)
                if query is None:
                    continue

                query_text = f"{query.name} {query.pubmed_query}"
                vectors = await self._svc.embed_texts([query_text])
                query_vector = vectors[0]

                # Bulk update via pgvector cosine distance
                await self._db.execute(
                    text(
                        """
                        UPDATE articles
                        SET relevance_score = 1 - (
                            ae.embedding <=> CAST(:qvec AS vector)
                        )
                        FROM article_embeddings ae
                        WHERE ae.article_id = articles.id
                          AND ae.embedding_type = 'abstract'
                          AND articles.id = ANY(:ids)
                        """
                    ),
                    {
                        "qvec": str(query_vector),
                        "ids": article_ids,
                    },
                )
                await self._db.commit()
                logger.info(
                    "Re-scored %d articles for query %s", len(article_ids), query_id
                )
            except Exception as exc:
                logger.warning("Re-scoring failed for query %s: %s", query_id, exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_pending(self, limit: int | None) -> list[Article]:
        """Articles that are extracted but have no embedding rows yet."""
        from sqlalchemy import exists

        embedded_subq = (
            select(ArticleEmbedding.article_id)
            .where(ArticleEmbedding.article_id == Article.id)
            .correlate(Article)
        )

        stmt = (
            select(Article)
            .where(Article.processing_status == "extracted")
            .where(~exists(embedded_subq))
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _load_picos(
        self, article_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, PicoExtraction]:
        """Return a {article_id: PicoExtraction} map for *article_ids*."""
        result = await self._db.execute(
            select(PicoExtraction).where(PicoExtraction.article_id.in_(article_ids))
        )
        return {p.article_id: p for p in result.scalars().all()}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _batched(iterable, n: int):
    """Yield successive n-sized chunks from iterable."""
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk
