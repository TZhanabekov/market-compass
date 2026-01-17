#!/usr/bin/env python3
"""Daily refresh job for Railway Cron.

Schedule:
- Run once per day in Railway Cron Jobs.

Behavior (cost-controlled):
- For each (country_code in the supported 11) × (Q=6 model+storage queries):
  - Call SerpAPI google_shopping (cached in Redis; cache miss triggers a paid call)
  - Upsert into raw_offers only (no direct writes to offers)
- After raw ingestion, run reconciliation in batches to promote eligible raw_offers -> offers.

Run (local / Railway):
  cd services/api
  python -m scripts.refresh_daily

Optional env vars:
  REFRESH_COUNTRIES="US,JP,DE,FR,HK,AE,GB,SG,KR,AU,CA"
  REFRESH_MODELS="iphone-16-pro,iphone-17-pro"
  REFRESH_STORAGES="256gb,512gb,1tb"
  RECONCILE_BATCH=2000
  RECONCILE_MAX_BATCHES=20
"""

import asyncio
import os
import sys
from dataclasses import asdict


# Ensure imports work when executed as a script/module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingestion import COUNTRY_GL_MAP, ingest_raw_offers_for_query  # noqa: E402
from app.services.reconciliation import reconcile_raw_offers  # noqa: E402
from app.stores.postgres import close_db, init_db, ping_db, get_session  # noqa: E402
from app.stores.redis import close_redis, init_redis  # noqa: E402


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    return [p.strip() for p in raw.split(",") if p.strip()]


def _model_to_query_part(model: str) -> str:
    parts = model.split("-")
    out: list[str] = []
    for p in parts:
        if p == "iphone":
            out.append("iPhone")
        elif p.isdigit():
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)


def _build_queries(models: list[str], storages: list[str]) -> list[str]:
    queries: list[str] = []
    for m in models:
        for s in storages:
            queries.append(f"{_model_to_query_part(m)} {s.upper()}")
    return queries


async def _run_reconcile_batches(batch_size: int, max_batches: int) -> dict:
    total = {
        "batches": 0,
        "scanned": 0,
        "created_offers": 0,
        "updated_raw_matches": 0,
        "skipped_no_sku": 0,
        "skipped_fx": 0,
        "llm_external_calls": 0,
        "llm_budget": 0,
        "llm_reused": 0,
        "llm_skipped_budget": 0,
    }
    for _ in range(max_batches):
        async with get_session() as session:
            stats, _debug = await reconcile_raw_offers(session=session, limit=batch_size)
        total["batches"] += 1
        total["scanned"] += stats.scanned
        total["created_offers"] += stats.created_offers
        total["updated_raw_matches"] += stats.updated_raw_matches
        total["skipped_no_sku"] += stats.skipped_no_sku
        total["skipped_fx"] += stats.skipped_fx
        total["llm_external_calls"] += stats.llm_external_calls
        total["llm_budget"] = stats.llm_budget  # budget is per-run, keep last
        total["llm_reused"] += stats.llm_reused
        total["llm_skipped_budget"] += stats.llm_skipped_budget

        # When fewer than batch_size rows were scanned, we've likely drained the queue.
        if stats.scanned < batch_size:
            break
    return total


async def main() -> None:
    # Initialize shared connections (same as API lifespan, but for a one-off cron run)
    await init_db()
    await ping_db()
    try:
        await init_redis()
    except Exception:
        # Cron can still run without Redis (but will be expensive and less safe).
        pass

    try:
        countries_default = sorted(COUNTRY_GL_MAP.keys())
        countries = _parse_csv_env("REFRESH_COUNTRIES", countries_default)
        models = _parse_csv_env("REFRESH_MODELS", ["iphone-16-pro", "iphone-17-pro"])
        storages = _parse_csv_env("REFRESH_STORAGES", ["256gb", "512gb", "1tb"])
        queries = _build_queries(models=models, storages=storages)

        reconcile_batch = int(os.getenv("RECONCILE_BATCH", "2000"))
        reconcile_max_batches = int(os.getenv("RECONCILE_MAX_BATCHES", "20"))

        # Raw-only ingestion
        raw_stats: list[dict] = []
        for cc in countries:
            for q in queries:
                s = await ingest_raw_offers_for_query(query=q, country_code=cc)
                raw_stats.append(asdict(s))

        # Promotion
        reconcile_totals = await _run_reconcile_batches(
            batch_size=reconcile_batch,
            max_batches=reconcile_max_batches,
        )

        # Final output for Railway logs (single JSON-ish blob)
        print(
            {
                "ok": True,
                "countries": countries,
                "queries": queries,
                "raw": {
                    "runs": len(raw_stats),
                    "total_results": sum(x["total_results"] for x in raw_stats),
                    "filtered_accessories": sum(x["filtered_accessories"] for x in raw_stats),
                    "upserted_raw_offers": sum(x["upserted_raw_offers"] for x in raw_stats),
                    "errors": sum(x["errors"] for x in raw_stats),
                },
                "reconcile": reconcile_totals,
            }
        )
    finally:
        await close_redis()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

