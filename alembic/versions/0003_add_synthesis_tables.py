"""Add evidence_syntheses and synthesis_articles tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-18
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_syntheses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinical_query_id UUID REFERENCES clinical_queries(id),
            pipeline_run_id UUID REFERENCES pipeline_runs(id),
            summary_text TEXT NOT NULL,
            evidence_grade VARCHAR(20),
            consensus_status VARCHAR(20),
            key_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
            evidence_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
            article_count INTEGER,
            synthesis_model VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS synthesis_articles (
            synthesis_id UUID REFERENCES evidence_syntheses(id),
            article_id UUID REFERENCES articles(id),
            inclusion_reason TEXT,
            weight FLOAT NOT NULL DEFAULT 1.0,
            PRIMARY KEY (synthesis_id, article_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_evidence_syntheses_query_id
            ON evidence_syntheses(clinical_query_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_evidence_syntheses_created_at
            ON evidence_syntheses(created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS synthesis_articles")
    op.execute("DROP TABLE IF EXISTS evidence_syntheses")
