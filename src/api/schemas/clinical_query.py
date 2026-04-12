import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClinicalQueryCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    pubmed_query: str
    mesh_terms: list[str] = Field(default_factory=list)
    min_relevance_score: float = Field(0.7, ge=0.0, le=1.0)
    max_results: int = Field(100, ge=1, le=500)
    is_active: bool = True
    schedule_cron: str = Field("0 6 * * 1", max_length=50)


class ClinicalQueryUpdate(BaseModel):
    """All fields optional — only supplied fields are written."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    pubmed_query: str | None = None
    mesh_terms: list[str] | None = None
    min_relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    max_results: int | None = Field(None, ge=1, le=500)
    is_active: bool | None = None
    schedule_cron: str | None = Field(None, max_length=50)


class ClinicalQueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    pubmed_query: str
    mesh_terms: list[str]
    min_relevance_score: float
    max_results: int
    is_active: bool
    schedule_cron: str
    created_at: datetime
    updated_at: datetime


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int


class ClinicalQueryListResponse(BaseModel):
    data: list[ClinicalQueryResponse]
    pagination: Pagination
