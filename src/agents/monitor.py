"""Monitor Agent — Phase 1.

Queries PubMed for articles matching a clinical query, deduplicates against
the database, scores relevance, and persists new articles with
``processing_status='pending'`` for downstream extraction.

Pipeline tracking
-----------------
Each invocation creates one :class:`~src.models.pipeline.PipelineRun` and one
``PipelineStep`` named ``"monitor"``.  Sub-step counts are stored in the
step's ``metadata`` column; high-level totals go on the run itself.
"""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.article import Article
from src.models.clinical_query import ClinicalQuery
from src.models.pipeline import PipelineRun, PipelineStep
from src.services.pubmed_client import ArticleData, PubMedClient

logger = logging.getLogger(__name__)

# Common English stop-words excluded from relevance keyword matching
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of with is are was were be been "
    "being have has had do does did will would could should may might must "
    "from by as into this that these those it its not no nor so yet both "
    "either neither than then when where who which what how all any each "
    "few more most other some such than too very can just than".split()
)


# ---------------------------------------------------------------------------
# Relevance scorer (keyword overlap — replaced by embeddings in Phase 3)
# ---------------------------------------------------------------------------

def _score_relevance(article: ArticleData, query: ClinicalQuery) -> float:
    """Compute keyword-overlap relevance between a ClinicalQuery and an article.

    Tokenises the clinical query text and counts how many distinct keywords
    appear in the article's title + abstract + MeSH headings.

    Returns:
        Float in ``[0.0, 1.0]``.  ``0.5`` when the query yields no keywords
        (edge case).
    """
    mesh_terms: list[str] = query.mesh_terms if isinstance(query.mesh_terms, list) else []

    query_text = " ".join(
        filter(
            None,
            [
                query.name,
                query.description or "",
                query.pubmed_query,
                " ".join(mesh_terms),
            ],
        )
    ).lower()

    keywords = {
        tok for tok in re.findall(r"\b[a-z]{3,}\b", query_text) if tok not in _STOPWORDS
    }

    if not keywords:
        return 0.5

    article_text = " ".join(
        filter(
            None,
            [
                article.title,
                article.abstract or "",
                " ".join(article.mesh_headings),
            ],
        )
    ).lower()

    matches = sum(1 for kw in keywords if kw in article_text)
    return round(min(matches / len(keywords), 1.0), 4)


# ---------------------------------------------------------------------------
# Pipeline lifecycle helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _create_run(
    db: AsyncSession, query: ClinicalQuery, trigger_type: str
) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        clinical_query_id=query.id,
        status="running",
        trigger_type=trigger_type,
        started_at=_utcnow(),
        meta={"query_name": query.name},
    )
    db.add(run)
    await db.flush()  # get the id without committing
    return run


async def _create_step(
    db: AsyncSession, run: PipelineRun, step_name: str
) -> PipelineStep:
    step = PipelineStep(
        id=uuid.uuid4(),
        pipeline_run_id=run.id,
        step_name=step_name,
        status="running",
        started_at=_utcnow(),
        meta={},
    )
    db.add(step)
    await db.flush()
    return step


async def _complete_step(
    db: AsyncSession, step: PipelineStep, items_processed: int, meta: dict
) -> None:
    step.status = "completed"
    step.completed_at = _utcnow()
    step.items_processed = items_processed
    step.meta = meta
    await db.flush()


async def _fail_step(
    db: AsyncSession, step: PipelineStep, error: Exception
) -> None:
    step.status = "failed"
    step.completed_at = _utcnow()
    step.error_message = str(error)
    await db.flush()


async def _complete_run(
    db: AsyncSession,
    run: PipelineRun,
    articles_found: int,
    articles_inserted: int,
) -> None:
    run.status = "completed"
    run.completed_at = _utcnow()
    run.articles_found = articles_found
    run.articles_extracted = articles_inserted
    await db.commit()


async def _fail_run(
    db: AsyncSession, run: PipelineRun, step: PipelineStep, error: Exception
) -> None:
    await _fail_step(db, step, error)
    run.status = "failed"
    run.completed_at = _utcnow()
    run.error_message = str(error)
    await db.commit()


# ---------------------------------------------------------------------------
# Monitor Agent
# ---------------------------------------------------------------------------

class MonitorAgent:
    """Fetch, deduplicate, score, and persist PubMed articles for one query.

    Usage::

        async with AsyncSessionLocal() as db:
            query = await db.get(ClinicalQuery, query_id)
            agent = MonitorAgent(db)
            run = await agent.run(query, trigger_type="api")
    """

    def __init__(
        self,
        db: AsyncSession,
        pubmed_client: PubMedClient | None = None,
    ) -> None:
        self._db = db
        self._pubmed = pubmed_client  # injected externally or created per-run

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        query: ClinicalQuery,
        trigger_type: str = "manual",
        max_results: int = 100,
        date_range: tuple[str, str] | None = None,
    ) -> PipelineRun:
        """Execute the full monitor pipeline step for *query*.

        Args:
            query: Active :class:`~src.models.clinical_query.ClinicalQuery`.
            trigger_type: ``"manual"``, ``"scheduled"``, or ``"api"``.
            max_results: Maximum PMIDs to retrieve from PubMed.
            date_range: Optional ``(mindate, maxdate)`` filter in
                ``"YYYY/MM/DD"`` format.

        Returns:
            The persisted :class:`~src.models.pipeline.PipelineRun` record.

        Raises:
            Re-raises any exception after marking the run/step as ``failed``
            and committing the error state.
        """
        logger.info(
            "MonitorAgent starting | query=%s (%s) trigger=%s",
            query.id,
            query.name,
            trigger_type,
        )

        run = await _create_run(self._db, query, trigger_type)
        step = await _create_step(self._db, run, "monitor")

        try:
            counts = await self._execute(run, step, query, max_results, date_range)
        except Exception as exc:
            logger.exception("MonitorAgent failed | query=%s run=%s", query.id, run.id)
            await _fail_run(self._db, run, step, exc)
            raise

        await _complete_run(
            self._db,
            run,
            articles_found=counts["pmids_found"],
            articles_inserted=counts["inserted"],
        )

        logger.info(
            "MonitorAgent done | run=%s found=%d new=%d inserted=%d skipped=%d",
            run.id,
            counts["pmids_found"],
            counts["pmids_new"],
            counts["inserted"],
            counts["below_threshold"],
        )
        return run

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    async def _execute(
        self,
        run: PipelineRun,
        step: PipelineStep,
        query: ClinicalQuery,
        max_results: int,
        date_range: tuple[str, str] | None,
    ) -> dict:
        async with self._pubmed_ctx() as pubmed:
            # --- 1. Search ---
            pmids = await pubmed.esearch(
                query.pubmed_query,
                max_results=max_results,
                date_range=date_range,
            )
            logger.info("Search returned %d PMIDs | run=%s", len(pmids), run.id)

            if not pmids:
                await _complete_step(self._db, step, 0, {"pmids_found": 0, "pmids_new": 0})
                return {"pmids_found": 0, "pmids_new": 0, "inserted": 0, "below_threshold": 0}

            # --- 2. Deduplicate ---
            new_pmids = await self._deduplicate(pmids)
            logger.info(
                "Deduplication: %d total, %d new | run=%s",
                len(pmids),
                len(new_pmids),
                run.id,
            )

            if not new_pmids:
                await _complete_step(
                    self._db,
                    step,
                    0,
                    {"pmids_found": len(pmids), "pmids_new": 0, "inserted": 0, "below_threshold": 0},
                )
                return {"pmids_found": len(pmids), "pmids_new": 0, "inserted": 0, "below_threshold": 0}

            # --- 3. Fetch full records ---
            articles = await pubmed.efetch(new_pmids)
            logger.info("Fetched %d article records | run=%s", len(articles), run.id)

            # --- 4. Score and insert ---
            inserted, below_threshold = await self._score_and_insert(articles, query)

        meta = {
            "pmids_found": len(pmids),
            "pmids_new": len(new_pmids),
            "articles_fetched": len(articles),
            "inserted": inserted,
            "below_threshold": below_threshold,
        }
        await _complete_step(self._db, step, inserted, meta)

        return {
            "pmids_found": len(pmids),
            "pmids_new": len(new_pmids),
            "inserted": inserted,
            "below_threshold": below_threshold,
        }

    @asynccontextmanager
    async def _pubmed_ctx(self) -> AsyncGenerator[PubMedClient, None]:
        """Yield the injected client or create (and close) one for this run."""
        if self._pubmed is not None:
            yield self._pubmed
        else:
            async with PubMedClient() as client:
                yield client

    async def _deduplicate(self, pmids: list[str]) -> list[str]:
        """Return only PMIDs not already present in the articles table."""
        result = await self._db.execute(
            select(Article.pmid).where(Article.pmid.in_(pmids))
        )
        existing: set[str] = {row[0] for row in result}
        return [p for p in pmids if p not in existing]

    async def _score_and_insert(
        self,
        articles: list[ArticleData],
        query: ClinicalQuery,
    ) -> tuple[int, int]:
        """Score relevance, filter by threshold, and bulk-insert new articles.

        Returns:
            ``(inserted_count, below_threshold_count)``
        """
        inserted = 0
        below_threshold = 0
        threshold: float = query.min_relevance_score if query.min_relevance_score is not None else 0.7

        for article_data in articles:
            score = _score_relevance(article_data, query)

            if score < threshold:
                below_threshold += 1
                logger.debug(
                    "Article PMID=%s score=%.3f below threshold=%.2f — skipped",
                    article_data.pmid,
                    score,
                    threshold,
                )
                continue

            db_article = Article(
                id=uuid.uuid4(),
                pmid=article_data.pmid,
                title=article_data.title,
                abstract=article_data.abstract,
                authors=[
                    {"name": a.name, "affiliation": a.affiliation}
                    for a in article_data.authors
                ],
                journal=article_data.journal,
                publication_date=article_data.publication_date,
                doi=article_data.doi,
                mesh_headings=article_data.mesh_headings,
                article_type=article_data.article_type,
                clinical_query_id=query.id,
                relevance_score=score,
                processing_status="pending",
            )
            self._db.add(db_article)
            inserted += 1

        # Flush all inserts together before the caller commits
        if inserted:
            await self._db.flush()

        logger.info(
            "Scored %d articles: %d inserted, %d below threshold (%.2f)",
            len(articles),
            inserted,
            below_threshold,
            threshold,
        )
        return inserted, below_threshold
