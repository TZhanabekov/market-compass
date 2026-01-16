"""add_condition_to_offers

Revision ID: 6c9233f33b34
Revises: c6581b221719
Create Date: 2026-01-16 16:37:20.150081

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c9233f33b34'
down_revision: Union[str, Sequence[str], None] = 'c6581b221719'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add condition column to offers table
    # Default to "new" for existing offers
    op.add_column('offers', sa.Column('condition', sa.String(length=20), nullable=False, server_default='new'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('offers', 'condition')
