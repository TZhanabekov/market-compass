#!/usr/bin/env python3
"""Reconcile raw_offers -> offers (deterministic-only).

Goal:
- Promote paid SerpAPI shopping results stored in `raw_offers` into normalized `offers`
  when we can deterministically match them to an existing Golden SKU.
- Do NOT use LLM here (step 1). Multi-variant and contract listings are not promoted.

Idempotency:
- raw_offers rows are matched via `matched_sku_id` and/or existing `offers.dedup_key`.
- offers are only created when no existing offer with the same dedup_key exists.

Usage:
  cd services/api
  DATABASE_URL='postgresql://user:pass@host:port/db' python -m scripts.reconcile_raw_offers

Optional env vars:
  RECONCILE_LIMIT=500
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.reconciliation import reconcile_raw_offers  # noqa: E402


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required (postgresql://...)")

    limit = int(os.getenv("RECONCILE_LIMIT", "500"))

    engine = create_async_engine(_async_url(database_url), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        stats, debug = await reconcile_raw_offers(session=session, limit=limit)
        await session.commit()
        print(stats)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

