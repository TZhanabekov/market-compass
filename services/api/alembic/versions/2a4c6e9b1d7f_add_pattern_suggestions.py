"""add_pattern_suggestions

Revision ID: 2a4c6e9b1d7f
Revises: 0c7a0d3c9a1e
Create Date: 2026-01-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a4c6e9b1d7f"
down_revision: Union[str, Sequence[str], None] = "0c7a0d3c9a1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pattern_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("match_count_last", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_size_last", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_count_max", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("examples_json", sa.Text(), nullable=True),
        sa.Column("last_run_id", sa.String(length=40), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_pattern_suggestions_kind"), "pattern_suggestions", ["kind"], unique=False)
    op.create_index(op.f("ix_pattern_suggestions_last_run_id"), "pattern_suggestions", ["last_run_id"], unique=False)
    op.create_index(
        "uq_pattern_suggestions_kind_phrase",
        "pattern_suggestions",
        ["kind", "phrase"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_pattern_suggestions_kind_phrase", table_name="pattern_suggestions")
    op.drop_index(op.f("ix_pattern_suggestions_last_run_id"), table_name="pattern_suggestions")
    op.drop_index(op.f("ix_pattern_suggestions_kind"), table_name="pattern_suggestions")
    op.drop_table("pattern_suggestions")

