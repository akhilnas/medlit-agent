"""Widen pico_extractions varchar columns to TEXT.

effect_size and confidence_interval were VARCHAR(200) which is too short
for LLM-generated descriptive text. p_value widened from VARCHAR(20) to
VARCHAR(50) as a precaution.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("pico_extractions", "effect_size", type_=sa.Text(), existing_nullable=True)
    op.alter_column(
        "pico_extractions", "confidence_interval", type_=sa.Text(), existing_nullable=True
    )
    op.alter_column(
        "pico_extractions", "p_value", type_=sa.String(50), existing_nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "pico_extractions", "effect_size", type_=sa.String(200), existing_nullable=True
    )
    op.alter_column(
        "pico_extractions",
        "confidence_interval",
        type_=sa.String(200),
        existing_nullable=True,
    )
    op.alter_column(
        "pico_extractions", "p_value", type_=sa.String(20), existing_nullable=True
    )
