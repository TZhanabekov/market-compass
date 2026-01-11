"""Golden SKU model.

A Golden SKU represents a canonical product configuration:
model + storage + color + condition (+ optional variants)

Example: "iphone-16-pro-256gb-black-new"
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base


class GoldenSku(Base):
    """Golden SKU - canonical product configuration."""

    __tablename__ = "golden_skus"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Stable SKU key (e.g., "iphone-16-pro-256gb-black-new")
    sku_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    # Parsed attributes
    model: Mapped[str] = mapped_column(String(50))  # e.g., "iphone-16-pro"
    storage: Mapped[str] = mapped_column(String(20))  # e.g., "256gb"
    color: Mapped[str] = mapped_column(String(50))  # e.g., "black"
    condition: Mapped[str] = mapped_column(String(20), default="new")  # new/refurbished

    # Optional variants
    sim_variant: Mapped[str | None] = mapped_column(String(50))  # esim-only, dual-sim
    lock_state: Mapped[str | None] = mapped_column(String(50))  # unlocked, carrier-locked
    region_variant: Mapped[str | None] = mapped_column(String(10))  # us, eu, jp

    # Display info
    display_name: Mapped[str] = mapped_column(String(200))  # "iPhone 16 Pro 256GB Black"
    msrp_usd: Mapped[float | None] = mapped_column()  # MSRP for anomaly detection

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<GoldenSku {self.sku_key}>"
