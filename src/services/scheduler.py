"""APScheduler-based pipeline scheduler.

Schedules clinical queries to run on their configured cron expressions.
Controlled by the ``scheduler_enabled`` settings flag — set to ``False``
in tests to prevent background jobs from starting.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

if TYPE_CHECKING:
    from src.models.clinical_query import ClinicalQuery

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Wraps APScheduler AsyncIOScheduler to run the pipeline on a cron.

    Args:
        db_factory: Async callable that yields an AsyncSession. Used by the
            scheduled job to obtain a fresh DB session per run.
        enabled: When ``False`` (e.g. in tests) the scheduler never starts and
            all mutating methods are no-ops.
    """

    def __init__(
        self,
        *,
        db_factory: Callable[[], Awaitable],
        enabled: bool = True,
    ) -> None:
        self._db_factory = db_factory
        self._enabled = enabled
        self._scheduler = None  # created lazily in start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the APScheduler background thread."""
        if not self._enabled:
            return
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()
        logger.info("Pipeline scheduler started")

    def shutdown(self) -> None:
        """Gracefully stop the scheduler."""
        if not self._enabled or self._scheduler is None:
            return
        self._scheduler.shutdown()
        logger.info("Pipeline scheduler stopped")

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def schedule_query(self, query: "ClinicalQuery") -> None:
        """Register a cron job for *query*.

        Silently skips inactive queries or queries with no cron expression.
        """
        if not self._enabled or self._scheduler is None:
            return
        if not query.is_active:
            logger.debug("Skipping inactive query %s", query.id)
            return
        if not query.schedule_cron:
            logger.debug("Query %s has no schedule_cron — skipping", query.id)
            return

        job_id = _job_id(query.id)
        cron_parts = _parse_cron(query.schedule_cron)

        self._scheduler.add_job(
            self._run_pipeline_for_query,
            trigger="cron",
            id=job_id,
            replace_existing=True,
            kwargs={"query_id": query.id},
            **cron_parts,
        )
        logger.info(
            "Scheduled query %s (%s) with cron '%s'",
            query.id,
            query.name,
            query.schedule_cron,
        )

    def unschedule_query(self, query_id: uuid.UUID) -> None:
        """Remove the cron job for *query_id* (no-op if not scheduled)."""
        if not self._enabled or self._scheduler is None:
            return
        job_id = _job_id(query_id)
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass  # Job may not exist — that's fine

    # ------------------------------------------------------------------
    # Job callback
    # ------------------------------------------------------------------

    async def _run_pipeline_for_query(self, *, query_id: uuid.UUID) -> None:
        """Execute the full pipeline for a single query (runs inside APScheduler)."""
        from src.agents.embedder import EmbeddingAgent
        from src.agents.extractor import ExtractionAgent
        from src.agents.monitor import MonitorAgent
        from src.agents.orchestrator import Orchestrator
        from src.agents.synthesizer import SynthesisAgent
        from src.models.clinical_query import ClinicalQuery

        logger.info("Scheduled pipeline run starting for query %s", query_id)
        try:
            async for db in self._db_factory():
                query: ClinicalQuery | None = await db.get(ClinicalQuery, query_id)
                if query is None or not query.is_active:
                    logger.warning(
                        "Query %s not found or inactive — skipping scheduled run",
                        query_id,
                    )
                    return

                orch = Orchestrator(
                    db=db,
                    monitor_agent=MonitorAgent(db),
                    extractor_agent=ExtractionAgent(db),
                    embedder_agent=EmbeddingAgent(db),
                    synthesis_agent=SynthesisAgent(db),
                )
                final_state = await orch.run(query)
                logger.info(
                    "Scheduled pipeline run finished for query %s — phase=%s",
                    query_id,
                    final_state.phase,
                )
        except Exception as exc:
            logger.error(
                "Scheduled pipeline run failed for query %s: %s", query_id, exc
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_id(query_id: uuid.UUID) -> str:
    return f"pipeline_{query_id}"


def _parse_cron(cron_expr: str) -> dict:
    """Parse a 5-field cron expression into APScheduler kwargs.

    Format: ``minute hour day_of_month month day_of_week``
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"Expected 5-field cron expression, got {len(parts)} fields: '{cron_expr}'"
        )
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }
