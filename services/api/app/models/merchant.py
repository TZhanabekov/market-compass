"""Merchant model.

Represents known merchants with trust tiers and metadata.
Used for trust score calculation.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base
from app.services.trust import MerchantTier


class Merchant(Base):
    """Merchant with trust tier and metadata."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Merchant identification
    name: Mapped[str] = mapped_column(String(200), index=True)
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(200))

    # Trust tier
    tier: Mapped[MerchantTier] = mapped_column(
        Enum(MerchantTier),
        default=MerchantTier.UNKNOWN,
    )

    # Metadata
    country_code: Mapped[str | None] = mapped_column(String(2))
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_blacklisted: Mapped[bool] = mapped_column(default=False)

    # Physical presence
    has_physical_store: Mapped[bool] = mapped_column(default=False)
    address: Mapped[str | None] = mapped_column(String(500))

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
        return f"<Merchant {self.name} ({self.tier.value})>"
