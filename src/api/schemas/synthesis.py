"""Pydantic schemas for the evidence synthesis API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SynthesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinical_query_id: uuid.UUID | None
    pipeline_run_id: uuid.UUID | None
    summary_text: str
    evidence_grade: str | None
    consensus_status: str | None
    key_findings: list
    evidence_gaps: list
    article_count: int | None
    synthesis_model: str | None
    created_at: datetime


class SynthesisListResponse(BaseModel):
    data: list[SynthesisResponse]
    total: int
