"""Widen pico_extractions.p_value to TEXT.

VARCHAR(50) is too short for LLM-generated p-value descriptions
(e.g. 'p>0.05 (for ERG expression in low vs high Gleason grade groups)').

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("pico_extractions", "p_value", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column(
        "pico_extractions", "p_value", type_=sa.String(50), existing_nullable=True
    )
