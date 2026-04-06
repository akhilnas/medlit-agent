"""API routes for evidence syntheses."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.synthesis import SynthesisListResponse, SynthesisResponse
from src.core.database import get_db
from src.models.evidence_synthesis import EvidenceSynthesis

router = APIRouter(prefix="/syntheses", tags=["syntheses"])


@router.get("", response_model=SynthesisListResponse)
async def list_syntheses(
    query_id: uuid.UUID | None = Query(None, description="Filter by clinical query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> SynthesisListResponse:
    """List evidence syntheses, optionally filtered by clinical query."""
    stmt = select(EvidenceSynthesis).order_by(EvidenceSynthesis.created_at.desc())
    count_stmt = select(func.count()).select_from(EvidenceSynthesis)

    if query_id is not None:
        stmt = stmt.where(EvidenceSynthesis.clinical_query_id == query_id)
        count_stmt = count_stmt.where(EvidenceSynthesis.clinical_query_id == query_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    result = await db.execute(stmt.offset(offset).limit(limit))
    syntheses = result.scalars().all()

    return SynthesisListResponse(
        data=[SynthesisResponse.model_validate(s) for s in syntheses],
        total=total,
    )


@router.get("/{synthesis_id}", response_model=SynthesisResponse)
async def get_synthesis(
    synthesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SynthesisResponse:
    """Retrieve a single evidence synthesis by ID."""
    synthesis = await db.get(EvidenceSynthesis, synthesis_id)
    if synthesis is None:
        raise HTTPException(status_code=404, detail="Synthesis not found")
    return SynthesisResponse.model_validate(synthesis)
