"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- clinical_queries ---
    op.create_table(
        "clinical_queries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("pubmed_query", sa.Text(), nullable=False),
        sa.Column("mesh_terms", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("min_relevance_score", sa.Float(), server_default=sa.text("0.7")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "schedule_cron", sa.String(50), server_default=sa.text("'0 6 * * 1'")
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # --- pipeline_runs ---
    op.create_table(
        "pipeline_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("clinical_query_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(20), server_default=sa.text("'running'")),
        sa.Column("trigger_type", sa.String(20)),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("articles_found", sa.Integer(), server_default=sa.text("0")),
        sa.Column("articles_extracted", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["clinical_query_id"], ["clinical_queries.id"]),
    )

    # --- articles ---
    op.create_table(
        "articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pmid", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text()),
        sa.Column("authors", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("journal", sa.String(500)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("doi", sa.String(100)),
        sa.Column(
            "mesh_headings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("article_type", sa.String(100)),
        sa.Column("clinical_query_id", postgresql.UUID(as_uuid=True)),
        sa.Column("relevance_score", sa.Float()),
        sa.Column(
            "processing_status", sa.String(20), server_default=sa.text("'pending'")
        ),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("pmid", name="uq_articles_pmid"),
        sa.ForeignKeyConstraint(["clinical_query_id"], ["clinical_queries.id"]),
    )

    # --- pico_extractions ---
    op.create_table(
        "pico_extractions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("population", sa.Text()),
        sa.Column("intervention", sa.Text()),
        sa.Column("comparison", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("study_design", sa.String(50)),
        sa.Column("sample_size", sa.Integer()),
        sa.Column("effect_size", sa.String(200)),
        sa.Column("confidence_interval", sa.String(200)),
        sa.Column("p_value", sa.String(20)),
        sa.Column("evidence_level", sa.String(50)),
        sa.Column("extraction_model", sa.String(100)),
        sa.Column("extraction_confidence", sa.Float()),
        sa.Column("raw_llm_response", postgresql.JSONB()),
        sa.Column(
            "extracted_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("article_id", name="uq_pico_article_id"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
    )

    # --- article_embeddings (uses pgvector vector type) ---
    op.create_table(
        "article_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_type", sa.String(50), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),  # placeholder, altered below
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
    )
    # Replace placeholder text column with proper vector type
    op.execute("ALTER TABLE article_embeddings ALTER COLUMN embedding TYPE vector(768) USING NULL")

    # --- evidence_syntheses ---
    op.create_table(
        "evidence_syntheses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("clinical_query_id", postgresql.UUID(as_uuid=True)),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("evidence_grade", sa.String(20)),
        sa.Column("consensus_status", sa.String(20)),
        sa.Column(
            "key_findings", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "evidence_gaps", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("article_count", sa.Integer()),
        sa.Column("synthesis_model", sa.String(100)),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["clinical_query_id"], ["clinical_queries.id"]),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"]),
    )

    # --- synthesis_articles (join table, composite PK) ---
    op.create_table(
        "synthesis_articles",
        sa.Column("synthesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inclusion_reason", sa.Text()),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0")),
        sa.PrimaryKeyConstraint("synthesis_id", "article_id"),
        sa.ForeignKeyConstraint(["synthesis_id"], ["evidence_syntheses.id"]),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
    )

    # --- pipeline_steps ---
    op.create_table(
        "pipeline_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("items_processed", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"]),
    )

    # --- Indexes ---
    op.create_index("idx_articles_pmid", "articles", ["pmid"])
    op.create_index("idx_articles_query", "articles", ["clinical_query_id"])
    op.create_index("idx_articles_status", "articles", ["processing_status"])
    op.execute("CREATE INDEX idx_articles_date ON articles (publication_date DESC)")
    op.create_index("idx_pico_article", "pico_extractions", ["article_id"])
    op.create_index("idx_pico_study", "pico_extractions", ["study_design"])
    op.create_index("idx_embeddings_article", "article_embeddings", ["article_id"])
    op.execute(
        "CREATE INDEX idx_embeddings_ivfflat ON article_embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.create_index("idx_syntheses_query", "evidence_syntheses", ["clinical_query_id"])
    op.create_index("idx_pipeline_runs_status", "pipeline_runs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("idx_syntheses_query", table_name="evidence_syntheses")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_ivfflat")
    op.drop_index("idx_embeddings_article", table_name="article_embeddings")
    op.drop_index("idx_pico_study", table_name="pico_extractions")
    op.drop_index("idx_pico_article", table_name="pico_extractions")
    op.execute("DROP INDEX IF EXISTS idx_articles_date")
    op.drop_index("idx_articles_status", table_name="articles")
    op.drop_index("idx_articles_query", table_name="articles")
    op.drop_index("idx_articles_pmid", table_name="articles")

    op.drop_table("pipeline_steps")
    op.drop_table("synthesis_articles")
    op.drop_table("evidence_syntheses")
    op.drop_table("article_embeddings")
    op.drop_table("pico_extractions")
    op.drop_table("articles")
    op.drop_table("pipeline_runs")
    op.drop_table("clinical_queries")

    op.execute("DROP EXTENSION IF EXISTS vector")
