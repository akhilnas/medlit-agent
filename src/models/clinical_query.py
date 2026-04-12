import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base


class ClinicalQuery(Base):
    __tablename__ = "clinical_queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    pubmed_query: Mapped[str] = mapped_column(Text, nullable=False)
    mesh_terms: Mapped[dict] = mapped_column(JSONB, server_default="'[]'::jsonb")
    min_relevance_score: Mapped[float] = mapped_column(Float, server_default="0.7")
    max_results: Mapped[int] = mapped_column(Integer, server_default="100")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    schedule_cron: Mapped[str] = mapped_column(String(50), server_default="'0 6 * * 1'")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    articles: Mapped[list["Article"]] = relationship(back_populates="clinical_query")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="clinical_query")
    evidence_syntheses: Mapped[list["EvidenceSynthesis"]] = relationship(
        back_populates="clinical_query"
    )
