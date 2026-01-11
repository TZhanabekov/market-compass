"""Offer model.

Represents an individual offer from a merchant for a Golden SKU.
Contains pricing, availability, and merchant URL.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base


def generate_offer_id() -> str:
    """Generate unique offer ID."""
    return str(uuid4())


class Offer(Base):
    """Individual offer from a merchant."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Public offer ID (used in URLs)
    offer_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        default=generate_offer_id,
    )

    # Relations
    sku_id: Mapped[int] = mapped_column(ForeignKey("golden_skus.id"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"))

    # Dedup key (merchant + price + currency + url_hash)
    dedup_key: Mapped[str] = mapped_column(String(200), index=True)

    # Location
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    country: Mapped[str] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))

    # Pricing
    price: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3))
    price_usd: Mapped[float] = mapped_column(index=True)  # For ranking
    tax_refund_value: Mapped[float] = mapped_column(default=0)
    shipping_cost: Mapped[float] = mapped_column(default=0)
    import_duty: Mapped[float] = mapped_column(default=0)
    final_effective_price: Mapped[float] = mapped_column(index=True)  # For ranking

    # Display
    local_price_formatted: Mapped[str] = mapped_column(String(50))
    shop_name: Mapped[str] = mapped_column(String(200))

    # Trust & availability
    trust_score: Mapped[int] = mapped_column(index=True)  # 0-100
    availability: Mapped[str] = mapped_column(String(50))  # In Stock, Limited, Out of Stock

    # Product info
    sim_type: Mapped[str | None] = mapped_column(String(100))
    warranty: Mapped[str | None] = mapped_column(String(200))
    restriction_alert: Mapped[str | None] = mapped_column(Text)

    # URLs
    product_link: Mapped[str] = mapped_column(Text)  # Google Shopping link
    merchant_url: Mapped[str | None] = mapped_column(Text)  # Direct merchant link
    immersive_token: Mapped[str | None] = mapped_column(String(200))  # For lazy hydration

    # Guide steps (JSON array)
    guide_steps_json: Mapped[str | None] = mapped_column(Text)

    # Data quality flags
    unknown_shipping: Mapped[bool] = mapped_column(default=False)
    unknown_refund: Mapped[bool] = mapped_column(default=False)

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="serpapi")
    source_product_id: Mapped[str | None] = mapped_column(String(200))

    # Timestamps
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Offer {self.offer_id} ${self.price_usd:.2f}>"
