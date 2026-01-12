#!/usr/bin/env python3
"""Seed database with initial data.

Creates:
- Golden SKUs for iPhone models (16 Pro, 16 Pro Max, etc.)
- Merchants with trust tiers
- Sample offers for different countries

Architecture note:
- Data definitions are structured for easy extension (add new models via IPHONE_MODELS)
- Future: Admin panel will manage SKUs and merchants
- Seed script is idempotent (uses upsert logic)

Usage:
    cd services/api
    python -m scripts.seed
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import GoldenSku, Merchant, Offer
from app.services.dedup import compute_offer_dedup_key, compute_sku_key
from app.services.trust import MerchantTier

load_dotenv()

# ============================================================
# iPhone Model Definitions (extensible for future models)
# ============================================================
# Architecture: Each model has base info + storage/color variants
# Future: This could come from Admin panel or config file

IPHONE_MODELS = {
    "iphone-16-pro": {
        "display_name": "iPhone 16 Pro",
        "msrp_usd": 999,
        "storage_options": ["128gb", "256gb", "512gb", "1tb"],
        "color_options": ["black", "white", "natural", "desert"],
        "sim_variants": ["esim-physical", "esim-only", "dual-physical"],
    },
    "iphone-16-pro-max": {
        "display_name": "iPhone 16 Pro Max",
        "msrp_usd": 1199,
        "storage_options": ["256gb", "512gb", "1tb"],
        "color_options": ["black", "white", "natural", "desert"],
        "sim_variants": ["esim-physical", "esim-only", "dual-physical"],
    },
}

# Default SKU configurations to seed (subset of all possible combinations)
DEFAULT_SKUS = [
    # iPhone 16 Pro variants
    {"model": "iphone-16-pro", "storage": "128gb", "color": "black", "condition": "new"},
    {"model": "iphone-16-pro", "storage": "256gb", "color": "black", "condition": "new"},
    {"model": "iphone-16-pro", "storage": "256gb", "color": "natural", "condition": "new"},
    {"model": "iphone-16-pro", "storage": "512gb", "color": "black", "condition": "new"},
    {"model": "iphone-16-pro", "storage": "1tb", "color": "black", "condition": "new"},
    # iPhone 16 Pro Max variants
    {"model": "iphone-16-pro-max", "storage": "256gb", "color": "black", "condition": "new"},
    {"model": "iphone-16-pro-max", "storage": "512gb", "color": "black", "condition": "new"},
    {"model": "iphone-16-pro-max", "storage": "1tb", "color": "black", "condition": "new"},
]

# ============================================================
# Merchant Definitions
# ============================================================

MERCHANTS = [
    # Official stores
    {"name": "Apple Store", "normalized": "apple-store", "tier": MerchantTier.OFFICIAL, "domain": "apple.com", "has_physical": True},
    # Verified retailers
    {"name": "Bic Camera", "normalized": "bic-camera", "tier": MerchantTier.VERIFIED, "domain": "biccamera.com", "country": "JP", "has_physical": True},
    {"name": "Yodobashi Camera", "normalized": "yodobashi-camera", "tier": MerchantTier.VERIFIED, "domain": "yodobashi.com", "country": "JP", "has_physical": True},
    {"name": "Fortress HK", "normalized": "fortress-hk", "tier": MerchantTier.VERIFIED, "domain": "fortress.com.hk", "country": "HK", "has_physical": True},
    {"name": "Sharaf DG", "normalized": "sharaf-dg", "tier": MerchantTier.VERIFIED, "domain": "sharafdg.com", "country": "AE", "has_physical": True},
    {"name": "MediaMarkt", "normalized": "mediamarkt", "tier": MerchantTier.VERIFIED, "domain": "mediamarkt.de", "country": "DE", "has_physical": True},
    {"name": "Best Buy", "normalized": "best-buy", "tier": MerchantTier.VERIFIED, "domain": "bestbuy.com", "country": "US", "has_physical": True},
    # Marketplaces
    {"name": "Amazon", "normalized": "amazon", "tier": MerchantTier.MARKETPLACE, "domain": "amazon.com", "has_physical": False},
]

# ============================================================
# Sample Offers (for iPhone 16 Pro 256GB Black)
# ============================================================

SAMPLE_OFFERS = [
    # Japan - Bic Camera (best deal with tax refund)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "bic-camera",
        "country_code": "JP",
        "country": "Japan",
        "city": "Tokyo",
        "price": 159800,
        "currency": "JPY",
        "price_usd": 1066,
        "tax_refund_value": 145,
        "final_effective_price": 921,
        "local_price_formatted": "¥159,800",
        "availability": "In Stock",
        "trust_score": 98,
        "sim_type": "eSIM + Physical SIM",
        "warranty": "1-Year Apple Japan",
        "restriction_alert": "Camera shutter sound always on (J/A model)",
        "product_link": "https://www.biccamera.com/bc/item/iphone16pro",
        "guide_steps": [
            {"icon": "map-pin", "title": "Where to Buy", "desc": "Bic Camera Yurakucho. Show passport at checkout for tax-free price."},
            {"icon": "plane", "title": "Airport Refund", "desc": "Narita Terminal 2, 'Customs' counter before security. Goods must be sealed."},
            {"icon": "cpu", "title": "Hardware Check", "desc": "Verify Model A3102. Shutter sound is permanent."},
        ],
    },
    # USA - Apple Store Delaware (no tax)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "apple-store",
        "country_code": "US",
        "country": "United States",
        "city": "Delaware",
        "price": 1099,
        "currency": "USD",
        "price_usd": 1099,
        "tax_refund_value": 0,
        "final_effective_price": 1099,
        "local_price_formatted": "$1,099",
        "availability": "In Stock",
        "trust_score": 100,
        "sim_type": "eSIM Only (No Physical Slot)",
        "warranty": "1-Year Apple US",
        "restriction_alert": "Model LL/A - No physical SIM tray. US models are eSIM only.",
        "product_link": "https://www.apple.com/shop/buy-iphone/iphone-16-pro",
        "guide_steps": [
            {"icon": "map-pin", "title": "Tax-Free State", "desc": "Buy in Delaware or Oregon for 0% sales tax at register."},
            {"icon": "cpu", "title": "eSIM Only", "desc": "US models have no physical SIM tray. Ensure your carrier supports eSIM."},
        ],
    },
    # Hong Kong - Fortress (dual physical SIM)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "fortress-hk",
        "country_code": "HK",
        "country": "Hong Kong",
        "city": "Central",
        "price": 8599,
        "currency": "HKD",
        "price_usd": 1103,
        "tax_refund_value": 0,
        "final_effective_price": 1103,
        "local_price_formatted": "HK$8,599",
        "availability": "In Stock",
        "trust_score": 94,
        "sim_type": "Dual Physical SIM",
        "warranty": "1-Year Apple HK",
        "restriction_alert": "ZA/A model supports dual physical SIM slots.",
        "product_link": "https://www.fortress.com.hk/en/iphone-16-pro",
        "guide_steps": [
            {"icon": "map-pin", "title": "Where to Buy", "desc": "Fortress in Central or Apple Causeway Bay."},
            {"icon": "check", "title": "Free Port", "desc": "HK is a free port. No VAT, prices are already net."},
        ],
    },
    # UAE - Sharaf DG (VAT refund available)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "sharaf-dg",
        "country_code": "AE",
        "country": "UAE",
        "city": "Dubai",
        "price": 4299,
        "currency": "AED",
        "price_usd": 1170,
        "tax_refund_value": 55,
        "final_effective_price": 1115,
        "local_price_formatted": "AED 4,299",
        "availability": "In Stock",
        "trust_score": 92,
        "sim_type": "eSIM + Physical SIM",
        "warranty": "1-Year Apple ME",
        "restriction_alert": "FaceTime may be disabled. Usually activates outside UAE.",
        "product_link": "https://www.sharafdg.com/product/iphone-16-pro",
        "guide_steps": [
            {"icon": "plane", "title": "Planet Tax Free", "desc": "Scan QR code at Planet kiosks in DXB Terminal 3."},
            {"icon": "alert-triangle", "title": "FaceTime Note", "desc": "FaceTime is disabled in UAE but usually activates abroad."},
        ],
    },
    # Germany - MediaMarkt (EU pricing)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "mediamarkt",
        "country_code": "DE",
        "country": "Germany",
        "city": "Berlin",
        "price": 1229,
        "currency": "EUR",
        "price_usd": 1327,
        "tax_refund_value": 0,
        "final_effective_price": 1327,
        "local_price_formatted": "€1,229",
        "availability": "In Stock",
        "trust_score": 95,
        "sim_type": "eSIM + Physical SIM",
        "warranty": "2-Year EU Consumer Law",
        "restriction_alert": None,
        "product_link": "https://www.mediamarkt.de/iphone-16-pro",
        "guide_steps": [
            {"icon": "check", "title": "EU Warranty", "desc": "2-year EU consumer warranty included."},
            {"icon": "globe", "title": "EU Model", "desc": "Works globally with eSIM + physical SIM."},
        ],
    },
    # Japan - Yodobashi (alternative to Bic Camera)
    {
        "sku_key": "iphone-16-pro-256gb-black-new",
        "merchant": "yodobashi-camera",
        "country_code": "JP",
        "country": "Japan",
        "city": "Osaka",
        "price": 159800,
        "currency": "JPY",
        "price_usd": 1066,
        "tax_refund_value": 145,
        "final_effective_price": 921,
        "local_price_formatted": "¥159,800",
        "availability": "Limited",
        "trust_score": 96,
        "sim_type": "eSIM + Physical SIM",
        "warranty": "1-Year Apple Japan",
        "restriction_alert": "Camera shutter sound always on (J/A model)",
        "product_link": "https://www.yodobashi.com/iphone-16-pro",
        "guide_steps": [
            {"icon": "map-pin", "title": "Where to Buy", "desc": "Yodobashi Umeda in Osaka. Tax-free with passport."},
            {"icon": "plane", "title": "Airport Refund", "desc": "Kansai Airport customs counter before departure."},
        ],
    },
]


async def seed_database() -> None:
    """Seed database with initial data."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/market_compass",
    )

    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("🌱 Seeding database...")

        # 1. Seed Golden SKUs
        print("\n📱 Creating Golden SKUs...")
        sku_map = await seed_golden_skus(session)

        # 2. Seed Merchants
        print("\n🏪 Creating Merchants...")
        merchant_map = await seed_merchants(session)

        # 3. Seed Offers
        print("\n💰 Creating Offers...")
        await seed_offers(session, sku_map, merchant_map)

        await session.commit()
        print("\n✅ Database seeded successfully!")

    await engine.dispose()


async def seed_golden_skus(session: AsyncSession) -> dict[str, int]:
    """Seed Golden SKUs and return mapping of sku_key -> id."""
    sku_map: dict[str, int] = {}

    for sku_def in DEFAULT_SKUS:
        model_info = IPHONE_MODELS.get(sku_def["model"], {})
        sku_key = compute_sku_key(sku_def)
        display_name = f"{model_info.get('display_name', sku_def['model'])} {sku_def['storage'].upper()} {sku_def['color'].title()}"

        # Check if exists
        result = await session.execute(
            select(GoldenSku).where(GoldenSku.sku_key == sku_key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  ⏭️  {sku_key} (exists)")
            sku_map[sku_key] = existing.id
        else:
            sku = GoldenSku(
                sku_key=sku_key,
                model=sku_def["model"],
                storage=sku_def["storage"],
                color=sku_def["color"],
                condition=sku_def["condition"],
                display_name=display_name,
                msrp_usd=model_info.get("msrp_usd"),
            )
            session.add(sku)
            await session.flush()
            sku_map[sku_key] = sku.id
            print(f"  ✅ {sku_key}")

    return sku_map


async def seed_merchants(session: AsyncSession) -> dict[str, int]:
    """Seed Merchants and return mapping of normalized_name -> id."""
    merchant_map: dict[str, int] = {}

    for m in MERCHANTS:
        # Check if exists
        result = await session.execute(
            select(Merchant).where(Merchant.normalized_name == m["normalized"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  ⏭️  {m['name']} (exists)")
            merchant_map[m["normalized"]] = existing.id
        else:
            merchant = Merchant(
                name=m["name"],
                normalized_name=m["normalized"],
                domain=m.get("domain"),
                tier=m["tier"],
                country_code=m.get("country"),
                is_verified=m["tier"] in (MerchantTier.OFFICIAL, MerchantTier.VERIFIED),
                is_blacklisted=False,
                has_physical_store=m.get("has_physical", False),
            )
            session.add(merchant)
            await session.flush()
            merchant_map[m["normalized"]] = merchant.id
            print(f"  ✅ {m['name']} ({m['tier'].value})")

    return merchant_map


async def seed_offers(
    session: AsyncSession,
    sku_map: dict[str, int],
    merchant_map: dict[str, int],
) -> None:
    """Seed sample offers."""
    import json
    import uuid

    for offer_def in SAMPLE_OFFERS:
        sku_id = sku_map.get(offer_def["sku_key"])
        merchant_id = merchant_map.get(offer_def["merchant"])

        if not sku_id:
            print(f"  ⚠️  SKU not found: {offer_def['sku_key']}")
            continue

        dedup_key = compute_offer_dedup_key(
            merchant=offer_def["merchant"],
            price=offer_def["price"],
            currency=offer_def["currency"],
        )

        # Check if exists
        result = await session.execute(
            select(Offer).where(Offer.dedup_key == dedup_key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  ⏭️  {offer_def['merchant']} - {offer_def['country']} (exists)")
        else:
            offer = Offer(
                offer_id=str(uuid.uuid4()),
                sku_id=sku_id,
                merchant_id=merchant_id,
                dedup_key=dedup_key,
                country_code=offer_def["country_code"],
                country=offer_def["country"],
                city=offer_def.get("city"),
                price=offer_def["price"],
                currency=offer_def["currency"],
                price_usd=offer_def["price_usd"],
                tax_refund_value=offer_def.get("tax_refund_value", 0),
                shipping_cost=0,
                import_duty=0,
                final_effective_price=offer_def["final_effective_price"],
                local_price_formatted=offer_def["local_price_formatted"],
                shop_name=next(
                    (m["name"] for m in MERCHANTS if m["normalized"] == offer_def["merchant"]),
                    offer_def["merchant"],
                ),
                trust_score=offer_def["trust_score"],
                availability=offer_def["availability"],
                sim_type=offer_def.get("sim_type"),
                warranty=offer_def.get("warranty"),
                restriction_alert=offer_def.get("restriction_alert"),
                product_link=offer_def["product_link"],
                guide_steps_json=json.dumps(offer_def.get("guide_steps", [])),
                unknown_shipping=False,
                unknown_refund=False,
                source="seed",
            )
            session.add(offer)
            print(f"  ✅ {offer_def['merchant']} - {offer_def['country']} (${offer_def['final_effective_price']})")


if __name__ == "__main__":
    asyncio.run(seed_database())
