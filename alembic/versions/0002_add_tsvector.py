"""Add tsvector full-text search column to articles

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-18
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add search_vector column
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS search_vector tsvector")

    # Back-fill existing rows
    op.execute(
        "UPDATE articles "
        "SET search_vector = to_tsvector('english', "
        "    coalesce(title, '') || ' ' || coalesce(abstract, ''))"
    )

    # GIN index for fast full-text queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_tsvector "
        "ON articles USING gin(search_vector)"
    )

    # Trigger to auto-update search_vector on insert/update
    op.execute(
        """
        CREATE OR REPLACE FUNCTION articles_tsvector_trigger()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                to_tsvector('english',
                    coalesce(NEW.title, '') || ' ' || coalesce(NEW.abstract, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER tsvector_update
        BEFORE INSERT OR UPDATE ON articles
        FOR EACH ROW EXECUTE FUNCTION articles_tsvector_trigger()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON articles")
    op.execute("DROP FUNCTION IF EXISTS articles_tsvector_trigger()")
    op.execute("DROP INDEX IF EXISTS idx_articles_tsvector")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS search_vector")
