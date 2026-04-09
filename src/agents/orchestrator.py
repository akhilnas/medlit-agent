"""Pipeline Orchestrator — state-machine that runs all agents in sequence.

States: IDLE → MONITORING → EXTRACTING → EMBEDDING → SYNTHESIZING → COMPLETE / FAILED
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.agents.embedder import EmbeddingAgent
    from src.agents.extractor import ExtractionAgent
    from src.agents.monitor import MonitorAgent
    from src.agents.synthesizer import SynthesisAgent
    from src.models.clinical_query import ClinicalQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Immutable state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrchestratorState:
    """Immutable snapshot of the orchestrator's progress."""

    phase: str = "IDLE"
    articles_found: int = 0
    articles_extracted: int = 0
    articles_embedded: int = 0
    synthesis_id: uuid.UUID | None = None
    error: str | None = None

    def transition(self, phase: str, **updates) -> "OrchestratorState":
        """Return a new state with *phase* updated (and any additional fields)."""
        return replace(self, phase=phase, **updates)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """Runs the full pipeline for a clinical query.

    Agents are injected so the orchestrator can be tested without real DB/LLM
    calls.

    Args:
        db: Async SQLAlchemy session (passed through to agents if they need it,
            but the orchestrator itself does not query the DB).
        monitor_agent: MonitorAgent instance.
        extractor_agent: ExtractionAgent instance.
        embedder_agent: EmbeddingAgent instance.
        synthesis_agent: SynthesisAgent instance.
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        monitor_agent: "MonitorAgent",
        extractor_agent: "ExtractionAgent",
        embedder_agent: "EmbeddingAgent",
        synthesis_agent: "SynthesisAgent",
    ) -> None:
        self._db = db
        self._monitor = monitor_agent
        self._extractor = extractor_agent
        self._embedder = embedder_agent
        self._synthesizer = synthesis_agent

    async def run(self, query: "ClinicalQuery") -> OrchestratorState:
        """Execute the full pipeline and return the final state.

        Errors in the monitor step abort the pipeline with phase=FAILED.
        Errors in embed/synthesise steps are logged but do not propagate —
        the pipeline transitions to COMPLETE with partial results.
        """
        from src.core.metrics import articles_processed_total, pipeline_duration_seconds

        qid = str(query.id)
        state = OrchestratorState()

        # 1 — MONITORING
        state = state.transition("MONITORING")
        try:
            with pipeline_duration_seconds.labels(phase="monitor", query_id=qid).time():
                pipeline_run = await self._monitor.run(query, trigger_type="scheduled")
            state = state.transition(
                "MONITORING", articles_found=pipeline_run.articles_found
            )
            articles_processed_total.labels(status="found").inc(pipeline_run.articles_found)
            pipeline_run_id = pipeline_run.id
        except Exception as exc:
            logger.error("Monitor agent failed for query %s: %s", qid, exc)
            return state.transition("FAILED", error=str(exc))

        # 2 — EXTRACTING
        state = state.transition("EXTRACTING")
        try:
            with pipeline_duration_seconds.labels(phase="extract", query_id=qid).time():
                extract_stats = await self._extractor.run()
            extracted = extract_stats.get("extracted", 0)
            failed = extract_stats.get("failed", 0)
            state = state.transition("EXTRACTING", articles_extracted=extracted)
            articles_processed_total.labels(status="extracted").inc(extracted)
            articles_processed_total.labels(status="failed").inc(failed)
        except Exception as exc:
            logger.error("Extractor agent failed for query %s: %s", qid, exc)
            state = state.transition("EXTRACTING", articles_extracted=0)

        # 3 — EMBEDDING
        state = state.transition("EMBEDDING")
        try:
            with pipeline_duration_seconds.labels(phase="embed", query_id=qid).time():
                embed_stats = await self._embedder.run()
            embedded = embed_stats.get("embedded", 0)
            state = state.transition("EMBEDDING", articles_embedded=embedded)
            articles_processed_total.labels(status="embedded").inc(embedded)
        except Exception as exc:
            logger.warning("Embedder agent failed for query %s: %s", qid, exc)
            state = state.transition("EMBEDDING", articles_embedded=0)

        # 4 — SYNTHESIZING
        state = state.transition("SYNTHESIZING")
        try:
            await self._db.refresh(query)
            with pipeline_duration_seconds.labels(phase="synthesize", query_id=qid).time():
                synthesis = await self._synthesizer.run(
                    query, pipeline_run_id=pipeline_run_id
                )
            synthesis_id = synthesis.id if synthesis is not None else None
            state = state.transition("SYNTHESIZING", synthesis_id=synthesis_id)
        except Exception as exc:
            logger.error("Synthesis agent failed for query %s: %s", qid, exc)
            state = state.transition("SYNTHESIZING", synthesis_id=None)

        return state.transition("COMPLETE")
