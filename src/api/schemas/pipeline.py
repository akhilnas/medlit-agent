import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TriggerRequest(BaseModel):
    query_id: uuid.UUID
    trigger_type: Literal["api", "manual", "scheduled"] = "api"
    max_results: int = Field(100, ge=1, le=500)
    # Optional date window: "YYYY/MM/DD" strings forwarded to PubMed esearch
    min_date: str | None = Field(None, pattern=r"^\d{4}/\d{2}/\d{2}$")
    max_date: str | None = Field(None, pattern=r"^\d{4}/\d{2}/\d{2}$")


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinical_query_id: uuid.UUID | None
    status: str
    trigger_type: str | None
    started_at: datetime
    completed_at: datetime | None
    articles_found: int
    articles_extracted: int
    error_message: str | None
    meta: dict
