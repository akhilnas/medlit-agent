import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.embedder import EmbeddingAgent
from src.agents.extractor import ExtractionAgent
from src.agents.monitor import MonitorAgent
from src.agents.orchestrator import Orchestrator
from src.agents.synthesizer import SynthesisAgent
from src.api.schemas.pipeline import PipelineRunResponse, TriggerRequest
from src.core.database import get_db
from src.models.clinical_query import ClinicalQuery
from src.models.pipeline import PipelineRun

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class ExtractRequest(BaseModel):
    limit: int | None = Field(None, ge=1, description="Max articles to process (omit for all pending)")


class EmbedRequest(BaseModel):
    limit: int | None = Field(None, ge=1, description="Max articles to embed (omit for all)")


@router.post("/trigger", response_model=PipelineRunResponse, status_code=202)
async def trigger_pipeline(
    body: TriggerRequest,
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    """Trigger the Monitor Agent for the given clinical query.

    Fetches new PubMed articles, deduplicates, scores relevance, and persists
    them with ``processing_status='pending'``.  Blocks until the run completes
    so the response reflects the final ``status``, ``articles_found``, and
    ``articles_extracted`` counts.

    Returns 404 if the query does not exist, 422 if the query is inactive.
    """
    query: ClinicalQuery | None = await db.get(ClinicalQuery, body.query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")
    if not query.is_active:
        raise HTTPException(
            status_code=422,
            detail="Clinical query is inactive — set is_active=true before triggering",
        )

    date_range = None
    if body.min_date and body.max_date:
        date_range = (body.min_date, body.max_date)

    agent = MonitorAgent(db)
    run = await agent.run(
        query,
        trigger_type=body.trigger_type,
        max_results=body.max_results,
        date_range=date_range,
    )

    return PipelineRunResponse.model_validate(run)


@router.post("/extract", status_code=202)
async def trigger_extraction(
    body: ExtractRequest = ExtractRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the Extraction Agent against all pending articles.

    Calls Claude to extract PICO data for each article with
    ``processing_status='pending'`` and updates them to ``'extracted'``.

    Returns counts of extracted, failed, and skipped articles.
    """
    agent = ExtractionAgent(db)
    stats = await agent.run(limit=body.limit)
    return stats


@router.post("/embed", status_code=202)
async def trigger_embedding(
    body: EmbedRequest = EmbedRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Embed all extracted articles that don't yet have embeddings.

    Generates PubMedBERT vectors for ``abstract`` and ``pico`` text,
    stores them in ``article_embeddings``, and re-scores
    ``articles.relevance_score`` using cosine similarity.

    Returns counts of embedded, failed, and skipped articles.
    """
    agent = EmbeddingAgent(db)
    stats = await agent.run(limit=body.limit)
    return stats


class SynthesizeRequest(BaseModel):
    query_id: uuid.UUID = Field(..., description="Clinical query to synthesise")


@router.post("/synthesize", status_code=202)
async def trigger_synthesis(
    body: SynthesizeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the Synthesis Agent for a single clinical query.

    Loads the top-ranked extracted articles, calls Claude to synthesise
    evidence, and persists an EvidenceSynthesis record.

    Returns the synthesis ID, or ``{"synthesis_id": null}`` if there were
    no articles to synthesise.
    """
    query: ClinicalQuery | None = await db.get(ClinicalQuery, body.query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")

    agent = SynthesisAgent(db)
    synthesis = await agent.run(query)
    return {"synthesis_id": str(synthesis.id) if synthesis else None}


class RunRequest(BaseModel):
    query_id: uuid.UUID = Field(..., description="Clinical query to run the full pipeline for")


@router.post("/run", status_code=202)
async def run_full_pipeline(
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the full pipeline (Monitor → Extract → Embed → Synthesise) for a query.

    Blocks until all stages complete. Returns a summary of each stage's results
    and the final orchestrator phase (``COMPLETE`` or ``FAILED``).
    """
    query: ClinicalQuery | None = await db.get(ClinicalQuery, body.query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="Clinical query not found")
    if not query.is_active:
        raise HTTPException(
            status_code=422,
            detail="Clinical query is inactive — set is_active=true before running",
        )

    orch = Orchestrator(
        db=db,
        monitor_agent=MonitorAgent(db),
        extractor_agent=ExtractionAgent(db),
        embedder_agent=EmbeddingAgent(db),
        synthesis_agent=SynthesisAgent(db),
    )
    final_state = await orch.run(query)

    return {
        "phase": final_state.phase,
        "articles_found": final_state.articles_found,
        "articles_extracted": final_state.articles_extracted,
        "articles_embedded": final_state.articles_embedded,
        "synthesis_id": str(final_state.synthesis_id) if final_state.synthesis_id else None,
        "error": final_state.error,
    }


@router.get("/runs")
async def list_pipeline_runs(
    query_id: uuid.UUID | None = Query(None, description="Filter by clinical query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List pipeline run history with optional query filter."""
    stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc())
    if query_id is not None:
        stmt = stmt.where(PipelineRun.clinical_query_id == query_id)
    count_stmt = stmt.with_only_columns(PipelineRun.id)
    total_result = await db.execute(count_stmt)
    total = len(total_result.all())
    result = await db.execute(stmt.offset(offset).limit(limit))
    runs = result.scalars().all()
    return {
        "data": [
            {
                "id": str(r.id),
                "clinical_query_id": str(r.clinical_query_id) if r.clinical_query_id else None,
                "status": r.status,
                "trigger_type": r.trigger_type,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "articles_found": r.articles_found,
                "articles_extracted": r.articles_extracted,
                "error_message": r.error_message,
            }
            for r in runs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
