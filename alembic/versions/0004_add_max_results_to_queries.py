"""Add max_results column to clinical_queries.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-10
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clinical_queries
        ADD COLUMN IF NOT EXISTS max_results INTEGER NOT NULL DEFAULT 100
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE clinical_queries DROP COLUMN IF EXISTS max_results")
