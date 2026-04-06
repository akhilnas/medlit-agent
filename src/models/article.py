import uuid
from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from src.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    pmid: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[dict] = mapped_column(JSONB, server_default="'[]'::jsonb")
    journal: Mapped[str | None] = mapped_column(String(500))
    publication_date: Mapped[date | None] = mapped_column(Date)
    doi: Mapped[str | None] = mapped_column(String(100))
    mesh_headings: Mapped[dict] = mapped_column(JSONB, server_default="'[]'::jsonb")
    article_type: Mapped[str | None] = mapped_column(String(100))
    clinical_query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_queries.id")
    )
    relevance_score: Mapped[float | None] = mapped_column(Float)
    processing_status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    clinical_query: Mapped["ClinicalQuery | None"] = relationship(back_populates="articles")
    pico_extraction: Mapped["PicoExtraction | None"] = relationship(back_populates="article")
    embeddings: Mapped[list["ArticleEmbedding"]] = relationship(back_populates="article")
    synthesis_articles: Mapped[list["SynthesisArticle"]] = relationship(back_populates="article")
