"""add_pattern_phrases

Revision ID: 0c7a0d3c9a1e
Revises: 7f2a1c9d4e8b
Create Date: 2026-01-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0c7a0d3c9a1e"
down_revision: Union[str, Sequence[str], None] = "7f2a1c9d4e8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pattern_phrases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_pattern_phrases_kind"), "pattern_phrases", ["kind"], unique=False)
    op.create_index(op.f("ix_pattern_phrases_enabled"), "pattern_phrases", ["enabled"], unique=False)
    op.create_index(
        "uq_pattern_phrases_kind_phrase",
        "pattern_phrases",
        ["kind", "phrase"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_pattern_phrases_kind_phrase", table_name="pattern_phrases")
    op.drop_index(op.f("ix_pattern_phrases_enabled"), table_name="pattern_phrases")
    op.drop_index(op.f("ix_pattern_phrases_kind"), table_name="pattern_phrases")
    op.drop_table("pattern_phrases")

