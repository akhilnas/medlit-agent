"""Pydantic schemas for the semantic search API."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Free-text search query")
    embedding_type: Literal["abstract", "pico"] = Field(
        "abstract", description="Which embedding to search against"
    )
    limit: int = Field(10, ge=1, le=50)
    min_similarity: float = Field(0.0, ge=0.0, le=1.0, description="Minimum hybrid score threshold")
    # Optional metadata filters
    study_design: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class SearchResultItem(BaseModel):
    article_id: uuid.UUID
    pmid: str
    title: str
    journal: str | None
    publication_date: date | None
    relevance_score: float | None
    similarity_score: float
    vector_score: float
    fts_score: float
    study_design: str | None
    evidence_level: str | None


class SearchResponse(BaseModel):
    query: str
    embedding_type: str
    results: list[SearchResultItem]
    total: int
