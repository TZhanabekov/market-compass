"""add_pattern_suggestion_confidence

Revision ID: 5c1b8a0d2f6e
Revises: 2a4c6e9b1d7f
Create Date: 2026-01-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c1b8a0d2f6e"
down_revision: Union[str, Sequence[str], None] = "2a4c6e9b1d7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pattern_suggestions",
        sa.Column("llm_confidence_last", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pattern_suggestions",
        sa.Column("llm_confidence_max", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("pattern_suggestions", "llm_confidence_max")
    op.drop_column("pattern_suggestions", "llm_confidence_last")

