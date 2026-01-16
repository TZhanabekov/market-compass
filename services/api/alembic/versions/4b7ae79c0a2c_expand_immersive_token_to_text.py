"""expand_immersive_token_to_text

Revision ID: 4b7ae79c0a2c
Revises: 6c9233f33b34
Create Date: 2026-01-16 18:38:45.371949

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b7ae79c0a2c'
down_revision: Union[str, Sequence[str], None] = '6c9233f33b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change immersive_token from VARCHAR(200) to TEXT
    # SerpAPI immersive tokens can be very long (500+ chars)
    op.alter_column(
        'offers',
        'immersive_token',
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert to VARCHAR(200) - note: this may truncate data
    op.alter_column(
        'offers',
        'immersive_token',
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
