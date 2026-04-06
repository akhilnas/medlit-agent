"""Pydantic schemas for the articles API."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    population: str | None
    intervention: str | None
    comparison: str | None
    outcome: str | None
    study_design: str | None
    sample_size: int | None
    effect_size: str | None
    confidence_interval: str | None
    p_value: str | None
    evidence_level: str | None
    extraction_model: str | None
    extraction_confidence: float | None
    extracted_at: datetime


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pmid: str
    title: str
    abstract: str | None
    authors: Any  # list[dict] from JSONB
    journal: str | None
    publication_date: date | None
    doi: str | None
    mesh_headings: Any  # list[str] from JSONB
    article_type: str | None
    clinical_query_id: uuid.UUID | None
    relevance_score: float | None
    processing_status: str
    fetched_at: datetime
    created_at: datetime
    pico_extraction: PicoResponse | None


class ArticleListResponse(BaseModel):
    data: list[ArticleResponse]
    total: int
    limit: int
    offset: int
