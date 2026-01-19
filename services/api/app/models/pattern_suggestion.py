"""Pattern suggestion artifacts (from LLM suggest runs).

Stores recommended phrases and their observed match frequency on the sampled raw_offers.
This table is NOT used directly for detection; admin can promote selected suggestions
into `pattern_phrases` (the active ruleset) via /v1/admin/patterns.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.stores.postgres import Base


class PatternSuggestion(Base):
    __tablename__ = "pattern_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)

    kind: Mapped[str] = mapped_column(String(50), index=True)
    phrase: Mapped[str] = mapped_column(Text)

    # Match frequency from the latest suggest run
    match_count_last: Mapped[int] = mapped_column(Integer, default=0)
    sample_size_last: Mapped[int] = mapped_column(Integer, default=0)

    # Best observed match frequency across all runs
    match_count_max: Mapped[int] = mapped_column(Integer, default=0)

    # Small examples payload (JSON-serialized text)
    examples_json: Mapped[str | None] = mapped_column(Text)

    # Run metadata
    last_run_id: Mapped[str | None] = mapped_column(String(40), index=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

