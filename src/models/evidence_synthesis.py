import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base


class EvidenceSynthesis(Base):
    __tablename__ = "evidence_syntheses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    clinical_query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_queries.id")
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_grade: Mapped[str | None] = mapped_column(String(20))
    consensus_status: Mapped[str | None] = mapped_column(String(20))
    key_findings: Mapped[dict] = mapped_column(JSONB, server_default="'[]'::jsonb")
    evidence_gaps: Mapped[dict] = mapped_column(JSONB, server_default="'[]'::jsonb")
    article_count: Mapped[int | None] = mapped_column(Integer)
    synthesis_model: Mapped[str | None] = mapped_column(String(100))
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    clinical_query: Mapped["ClinicalQuery | None"] = relationship(
        back_populates="evidence_syntheses"
    )
    pipeline_run: Mapped["PipelineRun | None"] = relationship(back_populates="evidence_syntheses")
    synthesis_articles: Mapped[list["SynthesisArticle"]] = relationship(
        back_populates="synthesis"
    )


class SynthesisArticle(Base):
    __tablename__ = "synthesis_articles"

    synthesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_syntheses.id"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), primary_key=True
    )
    inclusion_reason: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, server_default="1.0")

    synthesis: Mapped["EvidenceSynthesis"] = relationship(back_populates="synthesis_articles")
    article: Mapped["Article"] = relationship(back_populates="synthesis_articles")
