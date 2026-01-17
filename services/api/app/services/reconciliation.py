"""Reconciliation service: raw_offers -> offers.

This is a deterministic-only step that promotes paid SerpAPI results captured in
`raw_offers` into normalized `offers` when we can confidently match them to an
existing Golden SKU.

Notes:
- This service does NOT call any LLM.
- Multi-variant and contract listings are not promoted.
- This is intentionally idempotent: it won't create duplicate offers if the
  same dedup_key already exists.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GoldenSku, Merchant, Offer, RawOffer
from app.services.attribute_extractor import extract_attributes
from app.services.dedup import compute_offer_dedup_key, compute_sku_key
from app.services.fx import FxRates, convert_to_usd, get_latest_fx_rates
from app.services.llm_parser import choose_sku_key_from_candidates
from app.services.trust import TrustFactors, calculate_trust_score, get_merchant_tier
from app.settings import get_settings

logger = logging.getLogger("uvicorn.error")


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


@dataclass
class ReconcileDebug:
    created_offer_ids: list[str]
    matched_raw_offer_ids: list[str]
    sample_reason_codes: list[str]


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


async def reconcile_raw_offers(
    *,
    session: AsyncSession,
    limit: int = 500,
    country_code: str | None = None,
    debug_sample_limit: int = 25,
) -> tuple[ReconcileStats, ReconcileDebug]:
    """Promote eligible raw_offers into offers.

    Args:
        session: DB session (caller controls commit/rollback).
        limit: Max number of unmatched raw_offers to scan.
        country_code: Optional filter by country_code.
        debug_sample_limit: Max number of sample IDs / reasons to return.

    Returns:
        Tuple of (stats, debug samples).
    """
    stats = ReconcileStats()
    created_offer_ids: list[str] = []
    matched_raw_offer_ids: list[str] = []
    sample_reason_codes: list[str] = []
    settings = get_settings()
    llm_calls = 0
    llm_calls_budget = min(
        int(limit * settings.llm_max_fraction_per_reconcile),
        int(settings.llm_max_calls_per_reconcile),
    )

    # FX is optional; if it fails, we still promote USD offers.
    fx_rates: FxRates | None = None
    try:
        fx_rates = await get_latest_fx_rates(base="USD")
    except Exception:
        fx_rates = None

    query = (
        select(RawOffer)
        .where(RawOffer.matched_sku_id.is_(None))
        .order_by(RawOffer.ingested_at.asc())
        .limit(limit)
    )
    if country_code:
        query = query.where(RawOffer.country_code == country_code.upper())

    res = await session.execute(query)
    raws = res.scalars().all()

    for raw in raws:
        stats.scanned += 1

        title = raw.title_raw or ""
        if not title:
            stats.skipped_missing_attrs += 1
            raw.match_reason_codes_json = json.dumps(["MISSING_TITLE"], ensure_ascii=False)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("MISSING_TITLE")
            continue

        is_multi_variant = _detect_is_multi_variant(title)
        is_contract = _detect_is_contract(title)
        if is_multi_variant:
            stats.skipped_multi_variant += 1
            raw.flags_json = json.dumps({"is_multi_variant": True, "is_contract": is_contract}, ensure_ascii=False)
            raw.match_reason_codes_json = json.dumps(["SKIP_MULTI_VARIANT"], ensure_ascii=False)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("SKIP_MULTI_VARIANT")
            continue
        if is_contract:
            stats.skipped_contract += 1
            raw.flags_json = json.dumps({"is_multi_variant": False, "is_contract": True}, ensure_ascii=False)
            raw.match_reason_codes_json = json.dumps(["SKIP_CONTRACT"], ensure_ascii=False)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("SKIP_CONTRACT")
            continue

        extraction = extract_attributes(title)
        model = extraction.attributes.get("model")
        storage = extraction.attributes.get("storage")
        color = extraction.attributes.get("color")
        condition = _normalize_condition(raw.second_hand_condition)

        # Snapshot parsed artifacts for later iterations/debugging.
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

        # Candidate-set matching: if deterministic extraction is incomplete,
        # optionally call LLM to choose an existing sku_key from candidates.
        if not model or not storage or not color:
            chosen_sku_key: str | None = None
            llm_payload: dict[str, Any] | None = None
            llm_conf: float | None = None

            if (
                settings.llm_enabled
                and settings.openai_api_key
                and model
                and llm_calls_budget > 0
                and llm_calls < llm_calls_budget
            ):
                cand_res = await session.execute(
                    select(GoldenSku.sku_key)
                    .where(GoldenSku.model == model)
                    .where(GoldenSku.condition == condition)
                    .limit(50)
                )
                candidates = [str(x) for x in cand_res.scalars().all()]
                llm_calls += 1
                llm_res = await choose_sku_key_from_candidates(
                    title=title,
                    second_hand_condition=raw.second_hand_condition,
                    merchant_name=raw.merchant_name,
                    candidates=candidates,
                )
                if llm_res:
                    chosen_sku_key = llm_res.sku_key
                    llm_payload = llm_res.raw
                    llm_conf = llm_res.match_confidence

            if not chosen_sku_key:
                stats.skipped_missing_attrs += 1
                raw.match_reason_codes_json = json.dumps(["MISSING_REQUIRED_ATTRS"], ensure_ascii=False)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("MISSING_REQUIRED_ATTRS")
                continue

            # Store LLM evidence into parsed snapshot for later auditing
            try:
                existing_snapshot = json.loads(raw.parsed_attrs_json or "{}")
                if isinstance(existing_snapshot, dict):
                    existing_snapshot["llm"] = llm_payload
                    raw.parsed_attrs_json = json.dumps(existing_snapshot, ensure_ascii=False)
            except Exception:
                pass

            sku = (await session.execute(select(GoldenSku).where(GoldenSku.sku_key == chosen_sku_key))).scalar_one_or_none()
            if not sku:
                stats.skipped_no_sku += 1
                raw.match_reason_codes_json = json.dumps(["SKU_NOT_IN_CATALOG"], ensure_ascii=False)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("SKU_NOT_IN_CATALOG")
                continue

            # Continue flow with resolved sku
            price_usd = await _convert_price_usd(price_local=raw.price_local, currency=raw.currency, fx_rates=fx_rates)
            if price_usd is None:
                stats.skipped_fx += 1
                raw.match_reason_codes_json = json.dumps(["FX_UNAVAILABLE"], ensure_ascii=False)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("FX_UNAVAILABLE")
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
                    raw.match_confidence = float(llm_conf or 0.0)
                    raw.match_reason_codes_json = json.dumps(["LLM_MATCH_EXISTING_OFFER"], ensure_ascii=False)
                    stats.updated_raw_matches += 1
                    if len(matched_raw_offer_ids) < debug_sample_limit:
                        matched_raw_offer_ids.append(raw.raw_offer_id)
                    if len(sample_reason_codes) < debug_sample_limit:
                        sample_reason_codes.append("LLM_MATCH_EXISTING_OFFER")
                else:
                    stats.dedup_conflict += 1
                    raw.match_reason_codes_json = json.dumps(["DEDUP_KEY_CONFLICT"], ensure_ascii=False)
                    if len(sample_reason_codes) < debug_sample_limit:
                        sample_reason_codes.append("DEDUP_KEY_CONFLICT")
                continue

            trust_score = calculate_trust_score(
                TrustFactors(
                    merchant_tier=merchant.tier,
                    has_shipping_info=False,
                    has_warranty_info=False,
                    has_return_policy=False,
                    price_within_expected_range=True,
                )
            )

            offer = Offer(
                offer_id=str(uuid4()),
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
                source="serpapi_reconcile_llm",
                source_product_id=raw.source_product_id,
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(offer)
            await session.flush()

            raw.matched_sku_id = sku.id
            raw.match_confidence = float(llm_conf or 0.0)
            raw.match_reason_codes_json = json.dumps(["LLM_MATCH"], ensure_ascii=False)

            stats.created_offers += 1
            stats.updated_raw_matches += 1

            if len(created_offer_ids) < debug_sample_limit:
                created_offer_ids.append(offer.offer_id)
            if len(matched_raw_offer_ids) < debug_sample_limit:
                matched_raw_offer_ids.append(raw.raw_offer_id)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("LLM_MATCH")
            continue

        sku_key = compute_sku_key({"model": model, "storage": storage, "color": color, "condition": condition})
        sku = (await session.execute(select(GoldenSku).where(GoldenSku.sku_key == sku_key))).scalar_one_or_none()
        if not sku:
            stats.skipped_no_sku += 1
            raw.match_reason_codes_json = json.dumps(["SKU_NOT_IN_CATALOG"], ensure_ascii=False)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("SKU_NOT_IN_CATALOG")
            continue

        price_usd = await _convert_price_usd(price_local=raw.price_local, currency=raw.currency, fx_rates=fx_rates)
        if price_usd is None:
            stats.skipped_fx += 1
            raw.match_reason_codes_json = json.dumps(["FX_UNAVAILABLE"], ensure_ascii=False)
            if len(sample_reason_codes) < debug_sample_limit:
                sample_reason_codes.append("FX_UNAVAILABLE")
            continue

        merchant = await _find_or_create_merchant(session, raw.merchant_name)
        dedup_key = compute_offer_dedup_key(
            merchant=raw.merchant_name,
            price=raw.price_local,
            currency=raw.currency,
            url=raw.product_link,
        )

        existing_offer = (await session.execute(select(Offer).where(Offer.dedup_key == dedup_key))).scalar_one_or_none()
        if existing_offer:
            if existing_offer.sku_id == sku.id:
                stats.matched_existing_offer += 1
                raw.matched_sku_id = sku.id
                raw.match_confidence = 1.0
                raw.match_reason_codes_json = json.dumps(["DEDUP_MATCH_EXISTING_OFFER"], ensure_ascii=False)
                stats.updated_raw_matches += 1
                if len(matched_raw_offer_ids) < debug_sample_limit:
                    matched_raw_offer_ids.append(raw.raw_offer_id)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("DEDUP_MATCH_EXISTING_OFFER")
            else:
                stats.dedup_conflict += 1
                raw.match_reason_codes_json = json.dumps(["DEDUP_KEY_CONFLICT"], ensure_ascii=False)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("DEDUP_KEY_CONFLICT")
            continue

        trust_score = calculate_trust_score(
            TrustFactors(
                merchant_tier=merchant.tier,
                has_shipping_info=False,
                has_warranty_info=False,
                has_return_policy=False,
                price_within_expected_range=True,
            )
        )

        offer = Offer(
            offer_id=str(uuid4()),
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

        if len(created_offer_ids) < debug_sample_limit:
            created_offer_ids.append(offer.offer_id)
        if len(matched_raw_offer_ids) < debug_sample_limit:
            matched_raw_offer_ids.append(raw.raw_offer_id)
        if len(sample_reason_codes) < debug_sample_limit:
            sample_reason_codes.append("DETERMINISTIC_SKU_MATCH")

    debug = ReconcileDebug(
        created_offer_ids=created_offer_ids,
        matched_raw_offer_ids=matched_raw_offer_ids,
        sample_reason_codes=sample_reason_codes,
    )
    return stats, debug

