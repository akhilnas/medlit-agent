"""Extraction Agent — Phase 2.

Fetches articles with ``processing_status='pending'``, calls Gemini to
extract PICO data, persists :class:`~src.models.pico_extraction.PicoExtraction`
records, and updates article status to ``'extracted'`` or ``'failed'``.

Articles are processed sequentially to avoid sharing a single
``AsyncSession`` across concurrent coroutines (not coroutine-safe in
SQLAlchemy async).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.article import Article
from src.models.pico_extraction import PicoExtraction
from src.services.gemini_client import GeminiClient
from src.services.pico_prompt import PicoPromptTemplate

logger = logging.getLogger(__name__)

# Evidence level mapping (study_design → Roman numeral grade)
EVIDENCE_LEVELS: dict[str, str] = {
    "meta_analysis": "I",
    "systematic_review": "I",
    "randomized_controlled_trial": "II",
    "cohort": "III",
    "case_control": "III",
    "cross_sectional": "IV",
    "case_report": "V",
    "case_series": "V",
    "other": "V",
}

_DEFAULT_CONCURRENCY = 5


class ExtractionAgent:
    """Run PICO extraction for all pending articles.

    Usage::

        async with AsyncSessionLocal() as db:
            agent = ExtractionAgent(db)
            stats = await agent.run(limit=50)
    """

    def __init__(
        self,
        db: AsyncSession,
        gemini_client: GeminiClient | None = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
    ) -> None:
        self._db = db
        self._llm = gemini_client or GeminiClient()
        # Concurrency param retained for backwards-compat with tests/callers,
        # but extraction now runs sequentially to avoid AsyncSession races.
        self._concurrency = concurrency

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, limit: int | None = None) -> dict:
        """Process pending articles sequentially.

        Sequential processing avoids all AsyncSession sharing races —
        exactly one coroutine touches the session at a time. LLM calls
        still benefit from async I/O but run one after another.

        Args:
            limit: Maximum number of articles to process in this run.
                   ``None`` means process all pending articles.

        Returns:
            Dict with keys: ``extracted``, ``failed``, ``skipped``, ``total_tokens``.
        """
        articles = await self._fetch_pending(limit)
        logger.info("ExtractionAgent: found %d pending articles", len(articles))

        extracted = failed = skipped = 0

        for article in articles:
            try:
                result = await self._process_article(article)
            except Exception as exc:
                logger.exception(
                    "Unhandled extractor error | pmid=%s error=%s",
                    article.pmid,
                    exc,
                )
                result = "failed"

            if result == "extracted":
                extracted += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        logger.info(
            "ExtractionAgent done | extracted=%d failed=%d skipped=%d total_tokens=%d",
            extracted,
            failed,
            skipped,
            self._llm.usage.total_tokens,
        )
        return {
            "extracted": extracted,
            "failed": failed,
            "skipped": skipped,
            "total_tokens": self._llm.usage.total_tokens,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_pending(self, limit: int | None) -> list[Article]:
        stmt = select(Article).where(Article.processing_status == "pending")
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _process_article(self, article: Article) -> str:
        """Extract PICO for one article.  Returns ``'extracted'``, ``'failed'``, or ``'skipped'``."""
        try:
            return await self._extract(article)
        except Exception as exc:
            logger.exception(
                "Extraction failed | pmid=%s article_id=%s error=%s",
                article.pmid,
                article.id,
                exc,
            )
            await self._mark_failed(article, str(exc))
            return "failed"

    async def _extract(self, article: Article) -> str:
        # Validate abstract presence before any DB or LLM work
        try:
            user_prompt = PicoPromptTemplate.render_user(article.title, article.abstract)
        except ValueError as exc:
            # No abstract — mark skipped (not an extraction error)
            logger.info("Skipping article PMID=%s: %s", article.pmid, exc)
            await self._mark_failed(article, str(exc))
            return "skipped"

        payload, call_usage = await self._llm.complete_json(
            system=PicoPromptTemplate.system(),
            user=user_prompt,
            max_tokens=4096,
        )

        result = PicoPromptTemplate.parse_response(payload)

        evidence_level = (
            EVIDENCE_LEVELS.get(result.study_design or "", "V") if result.study_design else None
        )

        pico = PicoExtraction(
            id=uuid.uuid4(),
            article_id=article.id,
            population=result.population,
            intervention=result.intervention,
            comparison=result.comparison,
            outcome=result.outcome,
            study_design=result.study_design,
            sample_size=result.sample_size,
            effect_size=result.effect_size,
            confidence_interval=result.confidence_interval,
            p_value=result.p_value,
            evidence_level=evidence_level,
            extraction_model=self._llm._model,
            extraction_confidence=result.extraction_confidence,
            raw_llm_response=payload,
            extracted_at=datetime.now(timezone.utc),
        )
        self._db.add(pico)
        article.processing_status = "extracted"
        await self._db.commit()

        logger.info(
            "Extracted PICO | pmid=%s design=%s evidence=%s tokens=%d",
            article.pmid,
            result.study_design,
            evidence_level,
            call_usage.total_tokens,
        )
        return "extracted"

    async def _mark_failed(self, article: Article, reason: str) -> None:
        """Mark an article as failed.

        Rollback is wrapped in try/except because it is only needed when a
        prior commit/flush left the session in a dirty state — callers
        from the "no abstract" path have not touched the session at all.
        """
        try:
            await self._db.rollback()
        except Exception:
            pass
        article.processing_status = "failed"
        try:
            await self._db.commit()
        except Exception as exc:
            logger.warning(
                "Failed to persist 'failed' status for PMID=%s: %s",
                article.pmid,
                exc,
            )
