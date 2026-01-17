"""RawOffer model.

RawOffer stores SerpAPI shopping results in a raw buffer so we don't discard paid
results when they don't match an existing Golden SKU (or are ambiguous).
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base


def generate_raw_offer_id() -> str:
    """Generate unique raw offer ID."""
    return str(uuid4())


class RawOffer(Base):
    """Raw ingestion buffer row."""

    __tablename__ = "raw_offers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Public raw offer ID (for internal references/debug)
    raw_offer_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        default=generate_raw_offer_id,
    )

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="serpapi_google_shopping")
    source_request_key: Mapped[str] = mapped_column(String(64), index=True)  # sha256 prefix
    source_product_id: Mapped[str | None] = mapped_column(String(200), index=True)

    # Location
    country_code: Mapped[str] = mapped_column(String(2), index=True)

    # Raw fields
    title_raw: Mapped[str] = mapped_column(Text)
    merchant_name: Mapped[str] = mapped_column(String(200))
    product_link: Mapped[str] = mapped_column(Text)
    product_link_hash: Mapped[str] = mapped_column(String(32), index=True)
    immersive_token: Mapped[str | None] = mapped_column(Text)
    second_hand_condition: Mapped[str | None] = mapped_column(String(50))
    thumbnail: Mapped[str | None] = mapped_column(Text)

    # Pricing
    price_local: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3))

    # Parsed artifacts (JSON-serialized text to keep migrations simple)
    parsed_attrs_json: Mapped[str | None] = mapped_column(Text)
    flags_json: Mapped[str | None] = mapped_column(Text)
    match_reason_codes_json: Mapped[str | None] = mapped_column(Text)

    # Optional resolution to Golden SKU
    matched_sku_id: Mapped[int | None] = mapped_column(ForeignKey("golden_skus.id"), index=True)
    match_confidence: Mapped[float | None] = mapped_column()

    # Timestamps
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

