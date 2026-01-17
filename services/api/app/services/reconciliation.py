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
import hashlib
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
from app.services.trust import TrustFactors, calculate_trust_score_with_reasons, get_merchant_tier
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
    # LLM metrics (for budgeting/monitoring)
    llm_budget: int = 0
    llm_external_calls: int = 0
    llm_reused: int = 0  # reused stored llm_chosen_sku_key without calling model
    llm_skipped_budget: int = 0  # would call LLM but budget exhausted


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
            # Korean
            "약정",
            "할부",
            "월",
            "요금제",
            "플랜",
            # Chinese
            "合約",
            "合约",
            "月費",
            "月费",
            "分期",
            "套餐",
            # Arabic
            "عقد",
            "خطة",
            "أقساط",
            "اقساط",
            "دفعات شهرية",
        ]
    )


def _json_load_or_empty(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _candidates_fingerprint(candidates: list[str]) -> str | None:
    if not candidates:
        return None
    h = hashlib.sha256()
    for c in candidates:
        h.update(c.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:40]


def _snapshot_parsed_attrs(
    *,
    existing_json: str | None,
    extraction,
    second_hand_condition: str | None,
    normalized_condition: str,
) -> str:
    """Merge deterministic snapshot into parsed_attrs_json without losing LLM fields."""
    snap = _json_load_or_empty(existing_json)
    snap["extraction"] = {
        "attributes": extraction.attributes,
        "confidence": extraction.confidence.value,
    }
    snap["second_hand_condition"] = second_hand_condition
    snap["normalized_condition"] = normalized_condition
    return json.dumps(snap, ensure_ascii=False)


def _get_llm_state(parsed_attrs_json: str | None) -> tuple[bool, str | None, float | None]:
    """Return (attempted, chosen_sku_key, match_confidence)."""
    snap = _json_load_or_empty(parsed_attrs_json)
    attempted = bool(snap.get("llm_attempted") is True)
    chosen = snap.get("llm_chosen_sku_key")
    chosen_s = str(chosen) if isinstance(chosen, str) and chosen.strip() else None
    conf = snap.get("llm_match_confidence")
    conf_f = float(conf) if isinstance(conf, (int, float)) else None
    return attempted, chosen_s, conf_f


def _mark_llm_attempt(
    parsed_attrs_json: str | None,
    *,
    candidates_count: int,
    candidates_fingerprint: str | None,
    llm_payload: dict[str, Any] | None,
    chosen_sku_key: str | None,
    match_confidence: float | None,
) -> str:
    snap = _json_load_or_empty(parsed_attrs_json)
    snap["llm_attempted"] = True
    snap["llm_candidates_count"] = candidates_count
    if candidates_fingerprint:
        snap["llm_candidates_fingerprint"] = candidates_fingerprint
    snap["llm_chosen_sku_key"] = chosen_sku_key
    snap["llm_match_confidence"] = match_confidence
    if llm_payload is not None:
        snap["llm"] = llm_payload
    return json.dumps(snap, ensure_ascii=False)


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
    llm_external_calls = 0
    llm_calls_budget = min(
        int(limit * settings.llm_max_fraction_per_reconcile),
        int(settings.llm_max_calls_per_reconcile),
    )
    stats.llm_budget = max(0, int(llm_calls_budget))

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
        raw.parsed_attrs_json = _snapshot_parsed_attrs(
            existing_json=raw.parsed_attrs_json,
            extraction=extraction,
            second_hand_condition=raw.second_hand_condition,
            normalized_condition=condition,
        )
        raw.flags_json = json.dumps({"is_multi_variant": False, "is_contract": False}, ensure_ascii=False)

        # Candidate-set matching: if deterministic extraction is incomplete,
        # optionally call LLM to choose an existing sku_key from candidates.
        if not model or not storage or not color:
            chosen_sku_key: str | None = None
            llm_payload: dict[str, Any] | None = None
            llm_conf: float | None = None
            llm_attempted, stored_choice, stored_conf = _get_llm_state(raw.parsed_attrs_json)
            if llm_attempted:
                chosen_sku_key = stored_choice
                llm_conf = stored_conf
                if chosen_sku_key:
                    stats.llm_reused += 1

            if (
                settings.llm_enabled
                and settings.openai_api_key
                and model
                and llm_calls_budget > 0
                and llm_external_calls < llm_calls_budget
                and not llm_attempted
            ):
                cand_res = await session.execute(
                    select(GoldenSku.sku_key)
                    .where(GoldenSku.model == model)
                    .where(GoldenSku.condition == condition)
                    .limit(50)
                )
                candidates = [str(x) for x in cand_res.scalars().all()]
                candidates_fingerprint = _candidates_fingerprint(candidates)
                llm_external_calls += 1
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
                # Mark attempt regardless of success to ensure we don't re-call next run.
                raw.parsed_attrs_json = _mark_llm_attempt(
                    raw.parsed_attrs_json,
                    candidates_count=len(candidates),
                    candidates_fingerprint=candidates_fingerprint,
                    llm_payload=llm_payload,
                    chosen_sku_key=chosen_sku_key,
                    match_confidence=llm_conf,
                )
            elif (
                settings.llm_enabled
                and settings.openai_api_key
                and model
                and not llm_attempted
                and llm_calls_budget > 0
                and llm_external_calls >= llm_calls_budget
            ):
                stats.llm_skipped_budget += 1

            if not chosen_sku_key:
                stats.skipped_missing_attrs += 1
                raw.match_reason_codes_json = json.dumps(["MISSING_REQUIRED_ATTRS"], ensure_ascii=False)
                if len(sample_reason_codes) < debug_sample_limit:
                    sample_reason_codes.append("MISSING_REQUIRED_ATTRS")
                continue

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

            trust_score, trust_reason_codes = calculate_trust_score_with_reasons(
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
                trust_reason_codes_json=json.dumps(trust_reason_codes, ensure_ascii=False),
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
                match_confidence=float(llm_conf or 0.0),
                match_reason_codes_json=json.dumps(["LLM_MATCH"], ensure_ascii=False),
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
            # If deterministic sku_key doesn't exist, try LLM fallback (candidate-set matching)
            # before declaring SKU_NOT_IN_CATALOG. This covers cases where a generic color token
            # was extracted (e.g. "blue") but the catalog uses a more specific color
            # (e.g. "deep-blue"), or when titles are non-English.
            chosen_sku_key: str | None = None
            llm_payload: dict[str, object] | None = None
            llm_conf: float | None = None

            if (
                settings.llm_enabled
                and settings.openai_api_key
                and model
                and llm_calls_budget > 0
                and llm_external_calls < llm_calls_budget
            ):
                llm_attempted, stored_choice, stored_conf = _get_llm_state(raw.parsed_attrs_json)
                if llm_attempted:
                    chosen_sku_key = stored_choice
                    llm_conf = stored_conf
                    if chosen_sku_key:
                        stats.llm_reused += 1
                else:
                    cand_query = (
                        select(GoldenSku.sku_key)
                        .where(GoldenSku.model == model)
                        .where(GoldenSku.condition == condition)
                    )
                    # If storage is known, narrow candidates further
                    if storage:
                        cand_query = cand_query.where(GoldenSku.storage == storage)
                    cand_res = await session.execute(cand_query.limit(50))
                    candidates = [str(x) for x in cand_res.scalars().all()]
                    candidates_fingerprint = _candidates_fingerprint(candidates)

                    llm_external_calls += 1
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
                    raw.parsed_attrs_json = _mark_llm_attempt(
                        raw.parsed_attrs_json,
                        candidates_count=len(candidates),
                        candidates_fingerprint=candidates_fingerprint,
                        llm_payload=llm_payload,
                        chosen_sku_key=chosen_sku_key,
                        match_confidence=llm_conf,
                    )
            elif (
                settings.llm_enabled
                and settings.openai_api_key
                and model
                and llm_calls_budget > 0
                and llm_external_calls >= llm_calls_budget
            ):
                stats.llm_skipped_budget += 1

            if chosen_sku_key:
                sku = (
                    await session.execute(select(GoldenSku).where(GoldenSku.sku_key == chosen_sku_key))
                ).scalar_one_or_none()
                if sku:
                    # Continue by falling through to the normal flow with resolved SKU.
                    # We treat this as a successful catalog match.
                    sku_key = chosen_sku_key
                else:
                    sku = None

            if sku is None:
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

        trust_score, trust_reason_codes = calculate_trust_score_with_reasons(
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
            trust_reason_codes_json=json.dumps(trust_reason_codes, ensure_ascii=False),
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
            match_confidence=1.0,
            match_reason_codes_json=json.dumps(["DETERMINISTIC_SKU_MATCH"], ensure_ascii=False),
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
    stats.llm_external_calls = int(llm_external_calls)
    return stats, debug

