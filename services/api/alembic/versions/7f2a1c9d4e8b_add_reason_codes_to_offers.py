"""add_reason_codes_to_offers

Revision ID: 7f2a1c9d4e8b
Revises: b3c1e8f0a2d7
Create Date: 2026-01-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2a1c9d4e8b"
down_revision: Union[str, Sequence[str], None] = "b3c1e8f0a2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Offer-level explainability artifacts (optional, stable).
    op.add_column("offers", sa.Column("match_confidence", sa.Float(), nullable=True))
    op.add_column("offers", sa.Column("match_reason_codes_json", sa.Text(), nullable=True))
    op.add_column("offers", sa.Column("trust_reason_codes_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "trust_reason_codes_json")
    op.drop_column("offers", "match_reason_codes_json")
    op.drop_column("offers", "match_confidence")

