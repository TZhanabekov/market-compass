"""add_raw_offers_table

Revision ID: 9b3f1a2d4c10
Revises: 6c9233f33b34
Create Date: 2026-01-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b3f1a2d4c10"
down_revision: Union[str, Sequence[str], None] = "6c9233f33b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_offer_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_request_key", sa.String(length=64), nullable=False),
        sa.Column("source_product_id", sa.String(length=200), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("title_raw", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.String(length=200), nullable=False),
        sa.Column("product_link", sa.Text(), nullable=False),
        sa.Column("product_link_hash", sa.String(length=32), nullable=False),
        sa.Column("immersive_token", sa.Text(), nullable=True),
        sa.Column("second_hand_condition", sa.String(length=50), nullable=True),
        sa.Column("thumbnail", sa.Text(), nullable=True),
        sa.Column("price_local", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("parsed_attrs_json", sa.Text(), nullable=True),
        sa.Column("flags_json", sa.Text(), nullable=True),
        sa.Column("match_reason_codes_json", sa.Text(), nullable=True),
        sa.Column("matched_sku_id", sa.Integer(), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["matched_sku_id"], ["golden_skus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_raw_offers_country_code"), "raw_offers", ["country_code"], unique=False)
    op.create_index(op.f("ix_raw_offers_matched_sku_id"), "raw_offers", ["matched_sku_id"], unique=False)
    op.create_index(op.f("ix_raw_offers_product_link_hash"), "raw_offers", ["product_link_hash"], unique=False)
    op.create_index(op.f("ix_raw_offers_raw_offer_id"), "raw_offers", ["raw_offer_id"], unique=True)
    op.create_index(op.f("ix_raw_offers_source_product_id"), "raw_offers", ["source_product_id"], unique=False)
    op.create_index(op.f("ix_raw_offers_source_request_key"), "raw_offers", ["source_request_key"], unique=False)

    # Idempotency constraints:
    # - Prefer SerpAPI product_id when present
    op.create_index(
        "uq_raw_offers_source_country_product_id",
        "raw_offers",
        ["source", "country_code", "source_product_id"],
        unique=True,
        postgresql_where=sa.text("source_product_id IS NOT NULL"),
    )
    # - Fallback to link hash when product_id missing or unstable
    op.create_index(
        "uq_raw_offers_source_country_link_hash",
        "raw_offers",
        ["source", "country_code", "product_link_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_raw_offers_source_country_link_hash", table_name="raw_offers")
    op.drop_index("uq_raw_offers_source_country_product_id", table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_source_request_key"), table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_source_product_id"), table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_raw_offer_id"), table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_product_link_hash"), table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_matched_sku_id"), table_name="raw_offers")
    op.drop_index(op.f("ix_raw_offers_country_code"), table_name="raw_offers")
    op.drop_table("raw_offers")

