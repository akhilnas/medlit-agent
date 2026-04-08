import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base


class PicoExtraction(Base):
    __tablename__ = "pico_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), unique=True, nullable=False
    )
    population: Mapped[str | None] = mapped_column(Text)
    intervention: Mapped[str | None] = mapped_column(Text)
    comparison: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    study_design: Mapped[str | None] = mapped_column(String(50))
    sample_size: Mapped[int | None] = mapped_column(Integer)
    effect_size: Mapped[str | None] = mapped_column(Text)
    confidence_interval: Mapped[str | None] = mapped_column(Text)
    p_value: Mapped[str | None] = mapped_column(String(50))
    evidence_level: Mapped[str | None] = mapped_column(String(50))
    extraction_model: Mapped[str | None] = mapped_column(String(100))
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    raw_llm_response: Mapped[dict | None] = mapped_column(JSONB)
    extracted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="pico_extraction")
