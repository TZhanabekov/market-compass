"""Admin-managed pattern phrases.

These phrases are used to detect:
- contract/plan listings (skip promotion to offers)
- condition hints (new/used/refurbished) from title/link (analytics + fallback)

Stored in DB so they can be updated without code changes.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base


class PatternPhrase(Base):
    __tablename__ = "pattern_phrases"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Kind examples:
    # - "contract"
    # - "condition_new"
    # - "condition_used"
    # - "condition_refurbished"
    kind: Mapped[str] = mapped_column(String(50), index=True)

    # Lowercased phrase (literal substring match; NOT regex).
    phrase: Mapped[str] = mapped_column(Text)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Optional provenance: "manual", "llm_suggested", etc.
    source: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

