import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    clinical_query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_queries.id")
    )
    status: Mapped[str] = mapped_column(String(20), server_default="'running'")
    trigger_type: Mapped[str | None] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    articles_found: Mapped[int] = mapped_column(Integer, server_default="0")
    articles_extracted: Mapped[int] = mapped_column(Integer, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    # 'metadata' is reserved by SQLAlchemy DeclarativeBase; map to the same DB column via name arg
    meta: Mapped[dict] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")

    clinical_query: Mapped["ClinicalQuery | None"] = relationship(back_populates="pipeline_runs")
    steps: Mapped[list["PipelineStep"]] = relationship(back_populates="pipeline_run")
    evidence_syntheses: Mapped[list["EvidenceSynthesis"]] = relationship(
        back_populates="pipeline_run"
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    items_processed: Mapped[int] = mapped_column(Integer, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, server_default="'{}'::jsonb")

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="steps")
