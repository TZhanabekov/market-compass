"""Explain/debug helpers for raw_offers parsing and matching decisions."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GoldenSku, RawOffer
from app.services.attribute_extractor import extract_attributes
from app.services.dedup import compute_sku_key
from app.settings import get_settings


def _json_load_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _json_load_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_condition(second_hand_condition: str | None) -> str:
    if not second_hand_condition:
        return "new"
    v = second_hand_condition.lower().strip()
    if v in ("refurbished", "refurb", "renewed", "certified pre-owned", "cpo"):
        return "refurbished"
    if v in ("used", "pre-owned", "second hand", "secondhand", "pre owned"):
        return "used"
    return "new"


async def get_raw_offer_by_ref(session: AsyncSession, raw_offer_ref: str) -> RawOffer | None:
    """Find RawOffer by numeric id or raw_offer_id string."""
    if raw_offer_ref.isdigit():
        res = await session.execute(select(RawOffer).where(RawOffer.id == int(raw_offer_ref)))
        return res.scalar_one_or_none()
    res = await session.execute(select(RawOffer).where(RawOffer.raw_offer_id == raw_offer_ref))
    return res.scalar_one_or_none()


async def explain_raw_offer(
    *,
    session: AsyncSession,
    raw_offer: RawOffer,
    include_candidates: bool = False,
    candidates_limit: int = 50,
) -> dict[str, Any]:
    settings = get_settings()
    title = raw_offer.title_raw or ""

    extraction = extract_attributes(title)
    attrs = extraction.attributes
    model = attrs.get("model")
    storage = attrs.get("storage")
    color = attrs.get("color")
    normalized_condition = _normalize_condition(raw_offer.second_hand_condition)

    deterministic_sku_key = None
    if model and storage and color:
        deterministic_sku_key = compute_sku_key(
            {"model": model, "storage": storage, "color": color, "condition": normalized_condition}
        )

    catalog_sku_exists = False
    if deterministic_sku_key:
        catalog_sku_exists = (
            (await session.execute(select(GoldenSku.id).where(GoldenSku.sku_key == deterministic_sku_key)))
            .scalar_one_or_none()
            is not None
        )

    parsed_snapshot = _json_load_dict(raw_offer.parsed_attrs_json)
    flags = _json_load_dict(raw_offer.flags_json)
    reason_codes = _json_load_list(raw_offer.match_reason_codes_json)

    llm_attempted = bool(parsed_snapshot.get("llm_attempted") is True)
    llm_choice = parsed_snapshot.get("llm_chosen_sku_key")
    llm_conf = parsed_snapshot.get("llm_match_confidence")
    llm_choice_s = str(llm_choice) if isinstance(llm_choice, str) and llm_choice.strip() else None
    llm_conf_f = float(llm_conf) if isinstance(llm_conf, (int, float)) else None

    candidates: list[str] = []
    if include_candidates and model:
        q = select(GoldenSku.sku_key).where(GoldenSku.model == model).where(GoldenSku.condition == normalized_condition)
        if storage:
            q = q.where(GoldenSku.storage == storage)
        res = await session.execute(q.limit(max(1, min(candidates_limit, 200))))
        candidates = [str(x) for x in res.scalars().all()]

    would_call_llm = (
        settings.llm_enabled
        and bool(settings.openai_api_key)
        and (not llm_attempted)
        and bool(model)
        and (
            # missing attrs OR deterministic key not in catalog
            (not (model and storage and color))
            or (deterministic_sku_key is not None and not catalog_sku_exists)
        )
    )

    return {
        "rawOffer": {
            "id": raw_offer.id,
            "rawOfferId": raw_offer.raw_offer_id,
            "source": raw_offer.source,
            "sourceProductId": raw_offer.source_product_id,
            "countryCode": raw_offer.country_code,
            "titleRaw": raw_offer.title_raw,
            "merchantName": raw_offer.merchant_name,
            "secondHandCondition": raw_offer.second_hand_condition,
            "priceLocal": raw_offer.price_local,
            "currency": raw_offer.currency,
            "matchedSkuId": raw_offer.matched_sku_id,
            "matchConfidence": raw_offer.match_confidence,
            "matchReasonCodes": reason_codes,
        },
        "deterministic": {
            "extractedAttrs": attrs,
            "confidence": extraction.confidence.value,
            "normalizedCondition": normalized_condition,
            "computedSkuKey": deterministic_sku_key,
        },
        "catalog": {
            "computedSkuKeyExists": catalog_sku_exists,
        },
        "llm": {
            "enabled": settings.llm_enabled,
            "attempted": llm_attempted,
            "chosenSkuKey": llm_choice_s,
            "matchConfidence": llm_conf_f,
            "candidatesCount": parsed_snapshot.get("llm_candidates_count"),
            "candidatesFingerprint": parsed_snapshot.get("llm_candidates_fingerprint"),
            "wouldCallNow": would_call_llm,
        },
        "debug": {
            "flags": flags,
            "parsedAttrsSnapshot": parsed_snapshot,
            "candidates": candidates if include_candidates else None,
        },
    }

