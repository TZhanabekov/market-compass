#!/usr/bin/env python3
"""Seed Golden SKUs for iPhone 16 and iPhone 17 families.

This script is intentionally idempotent: it upserts by sku_key.

Usage:
  cd services/api
  DATABASE_URL='postgresql://user:pass@host:port/db' python -m scripts.seed_iphone16_17_golden_skus

Notes:
- We do NOT auto-create Golden SKUs from ingestion. This is a curated catalog.
- Condition variants are created for: new / refurbished / used.
"""

import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add parent to path for imports (so `python -m scripts.*` works)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import GoldenSku  # noqa: E402
from app.services.dedup import compute_sku_key  # noqa: E402


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


CONDITIONS = ["new", "refurbished", "used"]

# Normalized colors used in sku_key (must match attribute extraction normalization)
IPHONE_FAMILIES: dict[str, dict] = {
    # iPhone 16 family (Apple specs)
    "iphone-16": {
        "display": "iPhone 16",
        "storages": ["128gb", "256gb", "512gb"],
        "colors": ["black", "white", "pink", "teal", "ultramarine"],
    },
    "iphone-16-plus": {
        "display": "iPhone 16 Plus",
        "storages": ["128gb", "256gb", "512gb"],
        "colors": ["black", "white", "pink", "teal", "ultramarine"],
    },
    "iphone-16-pro": {
        "display": "iPhone 16 Pro",
        "storages": ["128gb", "256gb", "512gb", "1tb"],
        "colors": ["black", "white", "natural", "desert"],
    },
    "iphone-16-pro-max": {
        "display": "iPhone 16 Pro Max",
        "storages": ["256gb", "512gb", "1tb"],
        "colors": ["black", "white", "natural", "desert"],
    },
    "iphone-16e": {
        "display": "iPhone 16e",
        "storages": ["128gb", "256gb", "512gb"],
        "colors": ["black", "white"],
    },
    # iPhone 17 family (Apple newsroom/specs, 2025)
    "iphone-17": {
        "display": "iPhone 17",
        "storages": ["256gb", "512gb"],
        "colors": ["black", "white", "mist-blue", "sage", "lavender"],
    },
    "iphone-17-air": {
        "display": "iPhone 17 Air",
        "storages": ["256gb", "512gb", "1tb"],
        "colors": ["space-black", "cloud-white", "sky-blue", "light-gold"],
    },
    "iphone-17-pro": {
        "display": "iPhone 17 Pro",
        "storages": ["256gb", "512gb", "1tb"],
        "colors": ["silver", "cosmic-orange", "deep-blue"],
    },
    "iphone-17-pro-max": {
        "display": "iPhone 17 Pro Max",
        "storages": ["256gb", "512gb", "1tb", "2tb"],
        "colors": ["silver", "cosmic-orange", "deep-blue"],
    },
}


def _display_color(color: str) -> str:
    mapping = {
        "black": "Black",
        "white": "White",
        "pink": "Pink",
        "teal": "Teal",
        "ultramarine": "Ultramarine",
        "natural": "Natural Titanium",
        "desert": "Desert Titanium",
        "silver": "Silver",
        "deep-blue": "Deep Blue",
        "cosmic-orange": "Cosmic Orange",
        "mist-blue": "Mist Blue",
        "sage": "Sage",
        "lavender": "Lavender",
        "space-black": "Space Black",
        "cloud-white": "Cloud White",
        "sky-blue": "Sky Blue",
        "light-gold": "Light Gold",
    }
    return mapping.get(color, color.replace("-", " ").title())


async def _upsert_sku(session: AsyncSession, *, model: str, storage: str, color: str, condition: str) -> str:
    attrs = {"model": model, "storage": storage, "color": color, "condition": condition}
    sku_key = compute_sku_key(attrs)

    existing = (
        await session.execute(select(GoldenSku).where(GoldenSku.sku_key == sku_key))
    ).scalar_one_or_none()

    display = IPHONE_FAMILIES[model]["display"]
    display_name = f"{display} {storage.upper()} {_display_color(color)} ({condition})"

    if existing:
        # Keep it stable but allow display_name refresh
        existing.display_name = display_name
        return sku_key

    session.add(
        GoldenSku(
            sku_key=sku_key,
            model=model,
            storage=storage,
            color=color,
            condition=condition,
            display_name=display_name,
            msrp_usd=None,
        )
    )
    return sku_key


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required (postgresql://...)")

    engine = create_async_engine(_async_url(database_url), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    created = 0
    updated = 0

    async with session_factory() as session:
        for model, info in IPHONE_FAMILIES.items():
            for storage in info["storages"]:
                for color in info["colors"]:
                    for condition in CONDITIONS:
                        sku_key = compute_sku_key(
                            {"model": model, "storage": storage, "color": color, "condition": condition}
                        )
                        exists = (
                            await session.execute(select(GoldenSku.id).where(GoldenSku.sku_key == sku_key))
                        ).scalar_one_or_none()
                        await _upsert_sku(
                            session,
                            model=model,
                            storage=storage,
                            color=color,
                            condition=condition,
                        )
                        if exists:
                            updated += 1
                        else:
                            created += 1

        await session.commit()

    await engine.dispose()
    print(f"Done. created={created}, updated={updated}")


if __name__ == "__main__":
    asyncio.run(main())

