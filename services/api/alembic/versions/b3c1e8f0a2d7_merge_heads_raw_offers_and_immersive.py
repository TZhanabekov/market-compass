"""merge_heads_raw_offers_and_immersive

This is a merge revision to resolve multiple Alembic heads:
- 4b7ae79c0a2c_expand_immersive_token_to_text
- 9b3f1a2d4c10_add_raw_offers_table

After this merge, `alembic upgrade head` becomes unambiguous.
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b3c1e8f0a2d7"
down_revision: Union[str, Sequence[str], None] = ("4b7ae79c0a2c", "9b3f1a2d4c10")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision: no schema changes.
    pass


def downgrade() -> None:
    # Downgrading a merge revision is a no-op.
    pass

