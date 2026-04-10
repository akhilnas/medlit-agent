"""Evidence Synthesis Agent.

Loads top-ranked extracted articles for a clinical query, calls the LLM to
synthesise the evidence, and persists an EvidenceSynthesis record.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.article import Article
from src.models.evidence_synthesis import EvidenceSynthesis
from src.models.pico_extraction import PicoExtraction
from src.services.gemini_client import GeminiClient
from src.services.synthesis_prompt import SynthesisPromptTemplate

if TYPE_CHECKING:
    from src.models.clinical_query import ClinicalQuery

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ARTICLES = 20
_DEFAULT_MIN_RELEVANCE = 0.0


class SynthesisAgent:
    """Synthesise evidence for a single clinical query.

    Args:
        db: Async SQLAlchemy session.
        llm_client: GeminiClient instance (injected for testing).
        max_articles: Maximum number of articles to include (sorted by
            relevance_score descending).
        min_relevance: Minimum relevance_score threshold.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        llm_client: GeminiClient | None = None,
        max_articles: int = _DEFAULT_MAX_ARTICLES,
        min_relevance: float = _DEFAULT_MIN_RELEVANCE,
    ) -> None:
        self._db = db
        self._llm = llm_client or GeminiClient()
        self._max_articles = max_articles
        self._min_relevance = min_relevance
        self._model_name = self._llm._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        query: "ClinicalQuery",
        *,
        pipeline_run_id: uuid.UUID | None = None,
    ) -> EvidenceSynthesis | None:
        """Synthesise evidence for *query*.

        Returns:
            The persisted :class:`EvidenceSynthesis` record, or ``None`` if
            there are no articles to synthesise or the LLM call fails.
        """
        articles = await self._fetch_articles(query.id)
        if not articles:
            logger.info("No articles to synthesise for query %s", query.id)
            return None

        picos_by_article = await self._load_picos(
            [a.id for a in articles]
        )

        article_dicts = [
            _article_to_dict(a, picos_by_article.get(a.id))
            for a in articles
        ]

        try:
            result = await self._call_llm(query.pubmed_query, article_dicts)
        except Exception as exc:
            logger.error(
                "Synthesis LLM call failed for query %s: %s", query.id, exc
            )
            return None

        synthesis = EvidenceSynthesis(
            clinical_query_id=query.id,
            pipeline_run_id=pipeline_run_id,
            summary_text=result.summary_text,
            evidence_grade=result.evidence_grade,
            consensus_status=result.consensus_status,
            key_findings=result.key_findings,
            evidence_gaps=result.evidence_gaps,
            article_count=len(articles),
            synthesis_model=self._model_name,
        )
        self._db.add(synthesis)
        await self._db.commit()
        await self._db.refresh(synthesis)

        logger.info(
            "Synthesis complete for query %s — %d articles, grade=%s",
            query.id,
            len(articles),
            result.evidence_grade,
        )
        return synthesis

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_articles(self, query_id: uuid.UUID) -> list[Article]:
        stmt = (
            select(Article)
            .where(Article.clinical_query_id == query_id)
            .where(Article.processing_status == "extracted")
            .where(Article.relevance_score >= self._min_relevance)
            .order_by(Article.relevance_score.desc())
            .limit(self._max_articles)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def _load_picos(
        self, article_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PicoExtraction]:
        stmt = select(PicoExtraction).where(
            PicoExtraction.article_id.in_(article_ids)
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return {p.article_id: p for p in rows}

    async def _call_llm(
        self,
        clinical_query: str,
        articles: list[dict],
    ):
        user_prompt = SynthesisPromptTemplate.render_user(
            clinical_query=clinical_query, articles=articles
        )
        payload, usage = await self._llm.complete_json(
            system=SynthesisPromptTemplate.system(),
            user=user_prompt,
            max_tokens=8192,
            temperature=0.0,
        )
        logger.debug(
            "Synthesis LLM tokens: in=%d out=%d",
            usage.input_tokens,
            usage.output_tokens,
        )
        return SynthesisPromptTemplate.parse_response(payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _article_to_dict(article: Article, pico: PicoExtraction | None) -> dict:
    d: dict = {
        "title": article.title or "",
        "abstract": article.abstract or "",
    }
    if pico is not None:
        d.update(
            {
                "intervention": pico.intervention,
                "population": pico.population,
                "comparison": pico.comparison,
                "outcome": pico.outcome,
                "study_design": pico.study_design,
                "effect_size": getattr(pico, "effect_size", None),
                "confidence_interval": getattr(pico, "confidence_interval", None),
                "p_value": getattr(pico, "p_value", None),
            }
        )
    return d
