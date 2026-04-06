"""Articles API — list with filters and semantic search."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas.article import ArticleListResponse, ArticleResponse
from src.api.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from src.core.database import get_db
from src.models.article import Article
from src.models.pico_extraction import PicoExtraction
from src.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/articles", tags=["articles"])

# Hybrid search weights
_VECTOR_WEIGHT = 0.7
_FTS_WEIGHT = 0.3

# ---------------------------------------------------------------------------
# Hybrid CTE query
# ---------------------------------------------------------------------------
_HYBRID_SEARCH_SQL = """
WITH
  vector_scores AS (
    SELECT
      ae.article_id,
      1 - (ae.embedding <=> CAST(:query_vector AS vector)) AS vec_sim
    FROM article_embeddings ae
    WHERE ae.embedding_type = :embedding_type
  ),
  fts_scores AS (
    SELECT
      a.id AS article_id,
      ts_rank(a.search_vector, plainto_tsquery('english', :query_text)) AS fts_rank
    FROM articles a
    WHERE a.search_vector @@ plainto_tsquery('english', :query_text)
  ),
  combined AS (
    SELECT
      a.id                           AS article_id,
      a.pmid,
      a.title,
      a.journal,
      a.publication_date,
      a.relevance_score,
      COALESCE(vs.vec_sim, 0.0)      AS vector_score,
      COALESCE(fs.fts_rank, 0.0)     AS fts_score,
      (:vector_weight * COALESCE(vs.vec_sim, 0.0)
       + :fts_weight  * COALESCE(fs.fts_rank, 0.0)) AS similarity_score,
      pe.study_design,
      pe.evidence_level
    FROM articles a
    LEFT JOIN vector_scores   vs ON vs.article_id = a.id
    LEFT JOIN fts_scores      fs ON fs.article_id = a.id
    LEFT JOIN pico_extractions pe ON pe.article_id = a.id
    WHERE vs.article_id IS NOT NULL
      AND (:vector_weight * COALESCE(vs.vec_sim, 0.0)
           + :fts_weight  * COALESCE(fs.fts_rank, 0.0)) >= :min_similarity
      AND (:study_design  IS NULL OR pe.study_design     = :study_design)
      AND (:date_from     IS NULL OR a.publication_date >= :date_from)
      AND (:date_to       IS NULL OR a.publication_date <= :date_to)
  )
SELECT * FROM combined
ORDER BY similarity_score DESC
LIMIT :limit
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=ArticleListResponse)
async def list_articles(
    processing_status: str | None = Query(None, description="Filter by processing_status"),
    study_design: str | None = Query(None, description="Filter by PICO study_design"),
    evidence_level: str | None = Query(None, description="Filter by PICO evidence_level"),
    clinical_query_id: uuid.UUID | None = Query(None, description="Filter by clinical_query_id (UUID)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    """Return a paginated list of articles with optional PICO data."""
    stmt = select(Article).options(selectinload(Article.pico_extraction))
    count_stmt = select(func.count()).select_from(Article)

    if processing_status is not None:
        stmt = stmt.where(Article.processing_status == processing_status)
        count_stmt = count_stmt.where(Article.processing_status == processing_status)

    if clinical_query_id is not None:
        stmt = stmt.where(Article.clinical_query_id == clinical_query_id)
        count_stmt = count_stmt.where(Article.clinical_query_id == clinical_query_id)

    if study_design is not None or evidence_level is not None:
        stmt = stmt.join(Article.pico_extraction)
        count_stmt = count_stmt.join(PicoExtraction, PicoExtraction.article_id == Article.id)
        if study_design is not None:
            stmt = stmt.where(PicoExtraction.study_design == study_design)
            count_stmt = count_stmt.where(PicoExtraction.study_design == study_design)
        if evidence_level is not None:
            stmt = stmt.where(PicoExtraction.evidence_level == evidence_level)
            count_stmt = count_stmt.where(PicoExtraction.evidence_level == evidence_level)

    stmt = stmt.order_by(Article.created_at.desc()).offset(offset).limit(limit)

    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    result = await db.execute(stmt)
    articles = list(result.scalars().all())

    return ArticleListResponse(
        data=[ArticleResponse.model_validate(a) for a in articles],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/search", response_model=SearchResponse)
async def search_articles(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Semantic + full-text hybrid search over embedded articles.

    Embeds *query* with PubMedBERT, performs cosine similarity search via
    pgvector, combines with PostgreSQL full-text rank using
    ``0.7 × semantic + 0.3 × keyword``, and returns ranked results.

    Only articles that have been embedded (via ``POST /pipeline/embed``)
    appear in results.
    """
    svc = EmbeddingService()
    try:
        vectors = await svc.embed_texts([body.query])
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {exc}") from exc

    query_vector = vectors[0]

    rows = await db.execute(
        text(_HYBRID_SEARCH_SQL),
        {
            "query_vector": str(query_vector),
            "query_text": body.query,
            "embedding_type": body.embedding_type,
            "vector_weight": _VECTOR_WEIGHT,
            "fts_weight": _FTS_WEIGHT,
            "min_similarity": body.min_similarity,
            "study_design": body.study_design,
            "date_from": body.date_from,
            "date_to": body.date_to,
            "limit": body.limit,
        },
    )

    results = [
        SearchResultItem(
            article_id=row.article_id,
            pmid=row.pmid,
            title=row.title,
            journal=row.journal,
            publication_date=row.publication_date,
            relevance_score=row.relevance_score,
            similarity_score=float(row.similarity_score),
            vector_score=float(row.vector_score),
            fts_score=float(row.fts_score),
            study_design=row.study_design,
            evidence_level=row.evidence_level,
        )
        for row in rows
    ]

    return SearchResponse(
        query=body.query,
        embedding_type=body.embedding_type,
        results=results,
        total=len(results),
    )
