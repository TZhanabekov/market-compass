"""Ingestion service: SerpAPI → attribute extraction → FX → dedup → DB.

This is the core pipeline for importing offers from SerpAPI into the database.

Flow:
1. Search SerpAPI google_shopping for a SKU query
2. Filter non-iPhone products (cases, screen protectors, etc.)
3. Extract attributes (model, storage, color, condition) via regex
4. Convert price to USD via FX service
5. Compute dedup key and check for duplicates
6. Match to existing Golden SKU or skip if no match
7. Calculate trust score
8. Persist offer to database

Cost control:
- Only call SerpAPI when cache is stale (TTL 1-6h)
- Never call immersive in bulk - only Top-N eager or lazy on CTA
"""

import logging
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GoldenSku, Merchant, Offer, RawOffer
from app.services.attribute_extractor import (
    ExtractionConfidence,
    extract_attributes,
    filter_non_iphone_products,
    is_iphone_product,
)
from app.services.dedup import compute_offer_dedup_key, compute_sku_key
from app.services.fx import FxRates, convert_to_usd, get_latest_fx_rates
from app.services.serpapi_client import ShoppingResult, get_serpapi_client
from app.services.trust import MerchantTier, TrustFactors, calculate_trust_score, get_merchant_tier
from app.stores.postgres import get_session

logger = logging.getLogger("uvicorn.error")


# ============================================================
# Country/Location Mapping
# ============================================================

# Country code -> Google Shopping gl parameter
COUNTRY_GL_MAP = {
    "JP": "jp",
    "US": "us",
    "HK": "hk",
    "AE": "ae",
    "DE": "de",
    "GB": "uk",
    "FR": "fr",
    "SG": "sg",
    "KR": "kr",
    "AU": "au",
    "CA": "ca",
}

# Country code -> currency
COUNTRY_CURRENCY_MAP = {
    "JP": "JPY",
    "US": "USD",
    "HK": "HKD",
    "AE": "AED",
    "DE": "EUR",
    "GB": "GBP",
    "FR": "EUR",
    "SG": "SGD",
    "KR": "KRW",
    "AU": "AUD",
    "CA": "CAD",
}

# Country code -> full name
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
    "CA": "Canada",
}


@dataclass
class IngestionStats:
    """Statistics from an ingestion run."""

    query: str
    country_code: str
    total_results: int
    filtered_accessories: int
    low_confidence: int
    no_sku_match: int
    duplicates: int
    new_offers: int
    updated_offers: int
    errors: int


@dataclass
class IngestionConfig:
    """Configuration for ingestion run."""

    min_confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    skip_low_confidence: bool = True
    update_existing: bool = True


async def ingest_offers_for_sku(
    sku_key: str,
    country_code: str,
    config: IngestionConfig | None = None,
) -> IngestionStats:
    """Ingest offers from SerpAPI for a specific SKU and country.

    Args:
        sku_key: Golden SKU key to search for.
        country_code: Country code (e.g., "JP", "US").
        config: Optional ingestion configuration.

    Returns:
        IngestionStats with counts of processed offers.
    """
    config = config or IngestionConfig()

    stats = IngestionStats(
        query=sku_key,
        country_code=country_code,
        total_results=0,
        filtered_accessories=0,
        low_confidence=0,
        no_sku_match=0,
        duplicates=0,
        new_offers=0,
        updated_offers=0,
        errors=0,
    )

    # Build search query from SKU key
    query = _sku_key_to_search_query(sku_key)
    gl = COUNTRY_GL_MAP.get(country_code.upper(), "us")
    # Stable request key for traceability/idempotency (mirrors SerpAPI cache key intent)
    source_request_key = hashlib.sha256(f"{query}:{gl}:en:".encode()).hexdigest()[:64]

    logger.info(f"Starting ingestion for SKU={sku_key}, country={country_code}, query={query}")

    # 1. Search SerpAPI
    client = get_serpapi_client()
    try:
        results = await client.search_shopping(query=query, gl=gl)
    except Exception as e:
        logger.error(f"SerpAPI search failed: {e}")
        stats.errors = 1
        return stats

    stats.total_results = len(results)
    logger.info(f"Got {len(results)} results from SerpAPI")

    if not results:
        return stats

    # 2. Get FX rates for price conversion
    try:
        fx_rates = await get_latest_fx_rates(base="USD")
        logger.info(f"FX rates available: {len(fx_rates.rates)} currencies, EUR={fx_rates.rates.get('EUR')}")
    except Exception as e:
        logger.error(f"Failed to fetch FX rates: {e}. All non-USD offers will be skipped!")
        fx_rates = None

    # 3. Process each result
    async with get_session() as session:
        # Find the target SKU
        sku = await _find_sku(session, sku_key)
        if not sku:
            logger.warning(f"No Golden SKU found for key={sku_key}")
            stats.no_sku_match = len(results)
            return stats

        for result in results:
            try:
                processed = await _process_shopping_result(
                    session=session,
                    result=result,
                    target_sku=sku,
                    country_code=country_code,
                    fx_rates=fx_rates,
                    config=config,
                    stats=stats,
                    source_request_key=source_request_key,
                )
            except Exception as e:
                logger.error(f"Error processing result {result.product_id}: {e}")
                stats.errors += 1

    logger.info(
        f"Ingestion complete: new={stats.new_offers}, updated={stats.updated_offers}, "
        f"filtered={stats.filtered_accessories}, duplicates={stats.duplicates}"
    )
    return stats


async def _process_shopping_result(
    session: AsyncSession,
    result: ShoppingResult,
    target_sku: GoldenSku,
    country_code: str,
    fx_rates: FxRates | None,
    config: IngestionConfig,
    stats: IngestionStats,
    source_request_key: str,
) -> bool:
    """Process a single shopping result.

    Returns:
        True if offer was created/updated, False otherwise.
    """
    # Filter non-iPhone products (cases, accessories, etc.)
    if not is_iphone_product(result.title):
        stats.filtered_accessories += 1
        return False

    if filter_non_iphone_products(result.title):
        stats.filtered_accessories += 1
        return False

    # Extract attributes (model, storage, color) from title
    extraction = extract_attributes(result.title)

    # Always persist a raw copy of the paid result (idempotent),
    # even if it won't match the target SKU.
    await _upsert_raw_offer(
        session=session,
        result=result,
        country_code=country_code,
        source_request_key=source_request_key,
        extraction=extraction,
    )

    # Get condition from SerpAPI second_hand_condition field (more reliable than title parsing)
    # If second_hand_condition is None → new, otherwise normalize the value
    condition = _normalize_condition(result.second_hand_condition)

    # Verify extracted condition matches target SKU condition
    if condition != target_sku.condition:
        stats.no_sku_match += 1
        return False

    # Skip low confidence if configured
    if config.skip_low_confidence:
        if extraction.confidence == ExtractionConfidence.LOW:
            stats.low_confidence += 1
            return False

    # Match to target SKU (simple check: model must match)
    if extraction.attributes.get("model") != target_sku.model:
        stats.no_sku_match += 1
        return False

    # Compute dedup key
    dedup_key = compute_offer_dedup_key(
        merchant=result.merchant,
        price=result.price,
        currency=result.currency,
        url=result.product_link,
    )

    # Check for existing offer
    existing = await _find_offer_by_dedup_key(session, dedup_key)
    if existing:
        if config.update_existing:
            await _update_offer(session, existing, result, country_code, fx_rates)
            stats.updated_offers += 1
            return True
        else:
            stats.duplicates += 1
            return False

    # Create new offer
    await _create_offer(
        session=session,
        result=result,
        sku=target_sku,
        country_code=country_code,
        dedup_key=dedup_key,
        fx_rates=fx_rates,
        extraction=extraction,
    )
    stats.new_offers += 1
    return True


def _hash_product_link(product_link: str) -> str:
    return hashlib.sha256(product_link.encode()).hexdigest()[:32]


def _detect_is_multi_variant(title: str) -> bool:
    """
    Multi-variant listings enumerate multiple storages/colors in one title,
    e.g. "256GB 512GB 1TB" or "256gb/512gb/1tb" or "All colors".
    """
    t = title.lower()
    # Storage enumeration: count distinct storage tokens
    storages = set()
    for amount, unit in re.findall(r"(\d+)\s*(gb|tb)", t):
        token = f"{amount}{unit}"
        if token in {"64gb", "128gb", "256gb", "512gb", "1tb", "2tb"}:
            storages.add(token)
    if len(storages) >= 2:
        return True
    # Common enumeration hints
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
            # German
            "vertrag",
            "ratenzahlung",
            "monatlich",
            # French
            "forfait",
            "abonnement",
            "mensualit",
            # Japanese
            "契約",
            "分割",
            "月額",
            "プラン",
        ]
    )


async def _upsert_raw_offer(
    session: AsyncSession,
    result: ShoppingResult,
    country_code: str,
    source_request_key: str,
    extraction,
) -> None:
    """
    Store raw SerpAPI result in raw_offers (idempotent).

    This does NOT change the existing offers/leaderboard flow; it just preserves
    paid results for later reconciliation and improved matching.
    """
    product_link_hash = _hash_product_link(result.product_link)
    is_multi_variant = _detect_is_multi_variant(result.title)
    is_contract = _detect_is_contract(result.title)

    # Serialize minimal parsed artifacts; keep schema flexible.
    flags = {
        "is_multi_variant": is_multi_variant,
        "is_contract": is_contract,
    }
    parsed_attrs = {
        "extraction": {
            "attributes": extraction.attributes,
            "confidence": extraction.confidence.value,
        },
        "second_hand_condition": result.second_hand_condition,
    }

    existing: RawOffer | None = None
    if result.product_id:
        res = await session.execute(
            select(RawOffer).where(
                RawOffer.source == "serpapi_google_shopping",
                RawOffer.country_code == country_code.upper(),
                RawOffer.source_product_id == result.product_id,
            )
        )
        existing = res.scalar_one_or_none()

    if existing is None:
        res = await session.execute(
            select(RawOffer).where(
                RawOffer.source == "serpapi_google_shopping",
                RawOffer.country_code == country_code.upper(),
                RawOffer.product_link_hash == product_link_hash,
            )
        )
        existing = res.scalar_one_or_none()

    if existing:
        existing.title_raw = result.title
        existing.merchant_name = result.merchant
        existing.product_link = result.product_link
        existing.immersive_token = result.immersive_token
        existing.second_hand_condition = result.second_hand_condition
        existing.thumbnail = result.thumbnail
        existing.price_local = result.price
        existing.currency = result.currency
        existing.flags_json = json.dumps(flags, ensure_ascii=False)
        existing.parsed_attrs_json = json.dumps(parsed_attrs, ensure_ascii=False)
        existing.source_request_key = source_request_key
        return

    session.add(
        RawOffer(
            source="serpapi_google_shopping",
            source_request_key=source_request_key,
            source_product_id=result.product_id or None,
            country_code=country_code.upper(),
            title_raw=result.title,
            merchant_name=result.merchant,
            product_link=result.product_link,
            product_link_hash=product_link_hash,
            immersive_token=result.immersive_token,
            second_hand_condition=result.second_hand_condition,
            thumbnail=result.thumbnail,
            price_local=result.price,
            currency=result.currency,
            parsed_attrs_json=json.dumps(parsed_attrs, ensure_ascii=False),
            flags_json=json.dumps(flags, ensure_ascii=False),
        )
    )


def _sku_key_to_search_query(sku_key: str) -> str:
    """Convert SKU key to a search query.

    Example: "iphone-16-pro-256gb-black-new" -> "iPhone 16 Pro 256GB"
    """
    parts = sku_key.split("-")

    # Extract model parts (iphone-16-pro or iphone-16-pro-max)
    model_parts = []
    storage = None
    i = 0

    while i < len(parts):
        part = parts[i]
        if part == "iphone":
            model_parts.append("iPhone")
        elif part.isdigit():
            model_parts.append(part)
        elif part in ("pro", "plus", "max"):
            model_parts.append(part.capitalize())
        elif part.endswith("gb") or part.endswith("tb"):
            storage = part.upper()
            break
        else:
            break
        i += 1

    query_parts = model_parts
    if storage:
        query_parts.append(storage)

    return " ".join(query_parts)


async def _find_sku(session: AsyncSession, sku_key: str) -> GoldenSku | None:
    """Find Golden SKU by key."""
    result = await session.execute(
        select(GoldenSku).where(GoldenSku.sku_key == sku_key)
    )
    return result.scalar_one_or_none()


async def _find_offer_by_dedup_key(session: AsyncSession, dedup_key: str) -> Offer | None:
    """Find existing offer by dedup key."""
    result = await session.execute(
        select(Offer).where(Offer.dedup_key == dedup_key)
    )
    return result.scalar_one_or_none()


async def _find_or_create_merchant(session: AsyncSession, merchant_name: str) -> Merchant | None:
    """Find or create merchant by name."""
    normalized = merchant_name.lower().strip()
    result = await session.execute(
        select(Merchant).where(Merchant.normalized_name == normalized)
    )
    merchant = result.scalar_one_or_none()

    if not merchant:
        # Create new merchant
        tier = get_merchant_tier(merchant_name)
        merchant = Merchant(
            name=merchant_name,
            normalized_name=normalized,
            tier=tier,  # MerchantTier enum, not string
        )
        session.add(merchant)
        await session.flush()

    return merchant


async def _create_offer(
    session: AsyncSession,
    result: ShoppingResult,
    sku: GoldenSku,
    country_code: str,
    dedup_key: str,
    fx_rates: FxRates | None,
    extraction,
) -> Offer:
    """Create new offer from shopping result."""
    # Get or create merchant
    merchant = await _find_or_create_merchant(session, result.merchant)

    # Convert price to USD
    price_usd = result.price
    if result.currency != "USD":
        if fx_rates:
            try:
                price_usd = await convert_to_usd(result.price, result.currency, rates=fx_rates)
            except Exception as e:
                logger.warning(
                    f"FX conversion failed for {result.currency} {result.price}: {e}. "
                    f"Skipping offer to avoid incorrect USD price."
                )
                raise ValueError(f"Cannot convert {result.currency} to USD: FX rates unavailable or invalid")
        else:
            # FX rates unavailable - cannot safely convert
            logger.warning(
                f"FX rates unavailable, cannot convert {result.currency} {result.price} to USD. "
                f"Skipping offer to avoid incorrect price_usd."
            )
            raise ValueError(f"Cannot convert {result.currency} to USD: FX rates unavailable")

    # Calculate trust score
    merchant_tier = get_merchant_tier(result.merchant)
    trust_factors = TrustFactors(
        merchant_tier=merchant_tier,
        has_shipping_info=False,  # Not available from google_shopping
        has_warranty_info=False,
        has_return_policy=False,
        price_within_expected_range=True,  # TODO: implement anomaly detection
    )
    trust_score = calculate_trust_score(trust_factors)

    # Format local price
    local_price_formatted = _format_local_price(result.price, result.currency)

    # Get condition from SerpAPI second_hand_condition (already normalized in _process_shopping_result)
    condition = _normalize_condition(result.second_hand_condition)

    offer = Offer(
        offer_id=str(uuid4()),
        sku_id=sku.id,
        merchant_id=merchant.id if merchant else None,
        dedup_key=dedup_key,
        country_code=country_code.upper(),
        country=COUNTRY_NAME_MAP.get(country_code.upper(), country_code),
        city=None,
        price=result.price,
        currency=result.currency,
        price_usd=round(price_usd, 2),
        tax_refund_value=0,
        shipping_cost=0,
        import_duty=0,
        final_effective_price=round(price_usd, 2),
        local_price_formatted=local_price_formatted,
        shop_name=result.merchant,
        trust_score=trust_score,
        availability="In Stock",  # Assume in stock from google_shopping
        condition=condition,  # new/refurbished/used
        sim_type=None,
        warranty=None,
        restriction_alert=None,
        product_link=result.product_link,
        merchant_url=None,
        immersive_token=result.immersive_token,
        guide_steps_json=None,
        unknown_shipping=True,
        unknown_refund=True,
        source="serpapi",
        source_product_id=result.product_id,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(offer)
    await session.flush()
    return offer


async def _update_offer(
    session: AsyncSession,
    offer: Offer,
    result: ShoppingResult,
    country_code: str,
    fx_rates: FxRates | None,
) -> None:
    """Update existing offer with fresh data."""
    # Convert price to USD
    price_usd = result.price
    if result.currency != "USD":
        if fx_rates:
            try:
                price_usd = await convert_to_usd(result.price, result.currency, rates=fx_rates)
            except Exception as e:
                logger.warning(
                    f"FX conversion failed for {result.currency} {result.price}: {e}. "
                    f"Keeping existing price_usd to avoid incorrect update."
                )
                # Don't update price_usd if conversion fails
                return
        else:
            logger.warning(
                f"FX rates unavailable, cannot convert {result.currency} {result.price} to USD. "
                f"Keeping existing price_usd to avoid incorrect update."
            )
            # Don't update price_usd if FX rates unavailable
            return

    offer.price = result.price
    offer.price_usd = round(price_usd, 2)
    offer.final_effective_price = round(price_usd, 2)
    offer.local_price_formatted = _format_local_price(result.price, result.currency)
    offer.condition = _normalize_condition(result.second_hand_condition)
    offer.updated_at = datetime.now(timezone.utc)


def _normalize_condition(second_hand_condition: str | None) -> str:
    """Normalize condition from SerpAPI second_hand_condition field.

    SerpAPI returns:
    - None → new (default)
    - "refurbished" → refurbished
    - "used" → used
    - "renewed" → refurbished (synonym)
    - Other values → normalize to closest match

    Args:
        second_hand_condition: Value from SerpAPI second_hand_condition field.

    Returns:
        Normalized condition: "new", "refurbished", or "used".
    """
    if not second_hand_condition:
        return "new"

    condition_lower = second_hand_condition.lower().strip()

    # Map common variations
    if condition_lower in ("refurbished", "refurb", "renewed", "certified pre-owned", "cpo"):
        return "refurbished"
    elif condition_lower in ("used", "pre-owned", "second hand", "secondhand"):
        return "used"
    else:
        # Unknown value - default to "new" for safety
        logger.warning(f"Unknown second_hand_condition value: {second_hand_condition}, defaulting to 'new'")
        return "new"


def _format_local_price(price: float, currency: str) -> str:
    """Format price with currency symbol."""
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

    # Format with thousands separator
    if currency in ("JPY", "KRW"):
        # No decimals for these currencies
        return f"{symbol}{price:,.0f}"
    else:
        return f"{symbol}{price:,.2f}"
