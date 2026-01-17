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
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import GoldenSku, Merchant, Offer, RawOffer  # noqa: E402
from app.services.attribute_extractor import extract_attributes  # noqa: E402
from app.services.dedup import compute_offer_dedup_key, compute_sku_key  # noqa: E402
from app.services.fx import FxRates, convert_to_usd, get_latest_fx_rates  # noqa: E402
from app.services.trust import TrustFactors, calculate_trust_score, get_merchant_tier  # noqa: E402


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


COUNTRY_NAME_MAP = {
    "JP": "Japan",
    "US": "United States",
    "HK": "Hong Kong",
    "AE": "United Arab Emirates",
    "DE": "Germany",
    "GB": "United Kingdom",
    "FR": "France",
    "SG": "Singapore",
    "KR": "South Korea",
    "AU": "Australia",
}


def _normalize_condition(second_hand_condition: str | None) -> str:
    if not second_hand_condition:
        return "new"
    v = second_hand_condition.lower().strip()
    if v in ("refurbished", "refurb", "renewed", "certified pre-owned", "cpo"):
        return "refurbished"
    if v in ("used", "pre-owned", "second hand", "secondhand", "pre owned"):
        return "used"
    # Unknown values: default to "new" (conservative, avoids excluding)
    return "new"


def _format_local_price(price: float, currency: str) -> str:
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "HKD": "HK$",
        "AED": "AED ",
        "SGD": "S$",
        "KRW": "₩",
        "AUD": "A$",
    }
    symbol = symbols.get(currency, f"{currency} ")
    if currency in ("JPY", "KRW"):
        return f"{symbol}{price:,.0f}"
    return f"{symbol}{price:,.2f}"


def _hash_product_link(product_link: str) -> str:
    return hashlib.sha256(product_link.encode()).hexdigest()[:32]


def _detect_is_multi_variant(title: str) -> bool:
    t = title.lower()
    storages = set()
    for amount, unit in re.findall(r"(\d+)\s*(gb|tb)", t):
        token = f"{amount}{unit}"
        if token in {"64gb", "128gb", "256gb", "512gb", "1tb", "2tb"}:
            storages.add(token)
    if len(storages) >= 2:
        return True
    if any(p in t for p in ["256gb/512gb", "512gb/1tb", "all colors", "all colour", "all color"]):
        return True
    return False


def _detect_is_contract(title: str) -> bool:
    t = title.lower()
    return any(
        p in t
        for p in [
            "with data plan",
            "with contract",
            "monthly payments",
            "installment payments",
            "mobile phone plan",
        ]
    )


@dataclass
class ReconcileStats:
    scanned: int = 0
    skipped_multi_variant: int = 0
    skipped_contract: int = 0
    skipped_missing_attrs: int = 0
    skipped_no_sku: int = 0
    skipped_fx: int = 0
    dedup_conflict: int = 0
    matched_existing_offer: int = 0
    created_offers: int = 0
    updated_raw_matches: int = 0


async def _find_or_create_merchant(session: AsyncSession, merchant_name: str) -> Merchant:
    normalized = merchant_name.lower().strip()
    res = await session.execute(select(Merchant).where(Merchant.normalized_name == normalized))
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    tier = get_merchant_tier(merchant_name)
    merchant = Merchant(name=merchant_name, normalized_name=normalized, tier=tier)
    session.add(merchant)
    await session.flush()
    return merchant


async def _convert_price_usd(
    *,
    price_local: float,
    currency: str,
    fx_rates: FxRates | None,
) -> float | None:
    if currency.upper() == "USD":
        return round(float(price_local), 2)
    if fx_rates is None:
        return None
    try:
        usd = await convert_to_usd(float(price_local), currency.upper(), rates=fx_rates)
        return round(float(usd), 2)
    except Exception:
        return None


async def reconcile_raw_offers(*, session: AsyncSession, limit: int = 500) -> ReconcileStats:
    stats = ReconcileStats()

    # FX is optional; if it fails, we still promote USD offers.
    fx_rates: FxRates | None = None
    try:
        fx_rates = await get_latest_fx_rates(base="USD")
    except Exception:
        fx_rates = None

    res = await session.execute(
        select(RawOffer)
        .where(RawOffer.matched_sku_id.is_(None))
        .order_by(RawOffer.ingested_at.asc())
        .limit(limit)
    )
    raws = res.scalars().all()

    for raw in raws:
        stats.scanned += 1

        title = raw.title_raw or ""
        if not title:
            stats.skipped_missing_attrs += 1
            continue

        is_multi_variant = _detect_is_multi_variant(title)
        is_contract = _detect_is_contract(title)
        if is_multi_variant:
            stats.skipped_multi_variant += 1
            raw.flags_json = json.dumps({"is_multi_variant": True, "is_contract": is_contract}, ensure_ascii=False)
            continue
        if is_contract:
            stats.skipped_contract += 1
            raw.flags_json = json.dumps({"is_multi_variant": False, "is_contract": True}, ensure_ascii=False)
            continue

        extraction = extract_attributes(title)
        model = extraction.attributes.get("model")
        storage = extraction.attributes.get("storage")
        color = extraction.attributes.get("color")
        condition = _normalize_condition(raw.second_hand_condition)

        # Update raw parsed snapshot (useful for later reconciliation iterations)
        raw.parsed_attrs_json = json.dumps(
            {
                "extraction": {
                    "attributes": extraction.attributes,
                    "confidence": extraction.confidence.value,
                },
                "second_hand_condition": raw.second_hand_condition,
                "normalized_condition": condition,
            },
            ensure_ascii=False,
        )
        raw.flags_json = json.dumps({"is_multi_variant": False, "is_contract": False}, ensure_ascii=False)

        if not model or not storage or not color:
            stats.skipped_missing_attrs += 1
            raw.match_reason_codes_json = json.dumps(["MISSING_REQUIRED_ATTRS"], ensure_ascii=False)
            continue

        sku_key = compute_sku_key({"model": model, "storage": storage, "color": color, "condition": condition})
        sku = (
            await session.execute(select(GoldenSku).where(GoldenSku.sku_key == sku_key))
        ).scalar_one_or_none()
        if not sku:
            stats.skipped_no_sku += 1
            raw.match_reason_codes_json = json.dumps(["SKU_NOT_IN_CATALOG"], ensure_ascii=False)
            continue

        # Convert price to USD; skip if FX unavailable for non-USD
        price_usd = await _convert_price_usd(price_local=raw.price_local, currency=raw.currency, fx_rates=fx_rates)
        if price_usd is None:
            stats.skipped_fx += 1
            raw.match_reason_codes_json = json.dumps(["FX_UNAVAILABLE"], ensure_ascii=False)
            continue

        merchant = await _find_or_create_merchant(session, raw.merchant_name)
        dedup_key = compute_offer_dedup_key(
            merchant=raw.merchant_name,
            price=raw.price_local,
            currency=raw.currency,
            url=raw.product_link,
        )

        existing_offer = (
            await session.execute(select(Offer).where(Offer.dedup_key == dedup_key))
        ).scalar_one_or_none()

        if existing_offer:
            if existing_offer.sku_id == sku.id:
                stats.matched_existing_offer += 1
                raw.matched_sku_id = sku.id
                raw.match_confidence = 1.0
                raw.match_reason_codes_json = json.dumps(["DEDUP_MATCH_EXISTING_OFFER"], ensure_ascii=False)
                stats.updated_raw_matches += 1
            else:
                stats.dedup_conflict += 1
                raw.match_reason_codes_json = json.dumps(["DEDUP_KEY_CONFLICT"], ensure_ascii=False)
            continue

        merchant_tier = merchant.tier
        trust_score = calculate_trust_score(
            TrustFactors(
                merchant_tier=merchant_tier,
                has_shipping_info=False,
                has_warranty_info=False,
                has_return_policy=False,
                price_within_expected_range=True,
            )
        )

        offer = Offer(
            offer_id=str(__import__("uuid").uuid4()),
            sku_id=sku.id,
            merchant_id=merchant.id,
            dedup_key=dedup_key,
            country_code=raw.country_code.upper(),
            country=COUNTRY_NAME_MAP.get(raw.country_code.upper(), raw.country_code.upper()),
            city=None,
            price=raw.price_local,
            currency=raw.currency.upper(),
            price_usd=price_usd,
            tax_refund_value=0,
            shipping_cost=0,
            import_duty=0,
            final_effective_price=price_usd,
            local_price_formatted=_format_local_price(raw.price_local, raw.currency.upper()),
            shop_name=raw.merchant_name,
            trust_score=trust_score,
            availability="In Stock",
            condition=condition,
            sim_type=None,
            warranty=None,
            restriction_alert=None,
            product_link=raw.product_link,
            merchant_url=None,
            immersive_token=raw.immersive_token,
            guide_steps_json=None,
            unknown_shipping=True,
            unknown_refund=True,
            source="serpapi_reconcile",
            source_product_id=raw.source_product_id,
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(offer)
        await session.flush()

        raw.matched_sku_id = sku.id
        raw.match_confidence = 1.0
        raw.match_reason_codes_json = json.dumps(["DETERMINISTIC_SKU_MATCH"], ensure_ascii=False)

        stats.created_offers += 1
        stats.updated_raw_matches += 1

    return stats


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required (postgresql://...)")

    limit = int(os.getenv("RECONCILE_LIMIT", "500"))

    engine = create_async_engine(_async_url(database_url), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        stats = await reconcile_raw_offers(session=session, limit=limit)
        await session.commit()
        print(stats)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

