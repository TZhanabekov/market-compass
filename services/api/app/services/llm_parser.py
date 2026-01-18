"""LLM parsing/matching (GPT-5-mini) - deterministic-first fallback.

This module is intentionally optional and off by default:
- It is used only when Settings.llm_enabled is True AND an API key is present.
- It uses Redis cache + lock to control cost and prevent request storms.

The LLM is constrained to choose from a provided candidate list (no hallucinated SKUs).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.settings import get_settings
from app.stores.redis import acquire_lock, cache_get, cache_set, release_lock

logger = logging.getLogger("uvicorn.error")

# Cache policy for LLM parsing (titles repeat heavily across runs)
TTL_LLM_PARSE = 180 * 24 * 3600  # 180 days
TTL_LLM_LOCK = 60  # seconds

PREFIX_LLM_PARSE = "llm:parse:"
PREFIX_LLM_LOCK = "llm:parse:"


class LlmMatch(BaseModel):
    sku_key: str = Field(..., description="Must be one of the provided candidates.")
    match_confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str | None = None


class LlmParseResponse(BaseModel):
    is_accessory: bool = False
    is_bundle: bool = False
    is_contract: bool = False
    match: LlmMatch


@dataclass(frozen=True)
class LlmChooseSkuResult:
    sku_key: str
    match_confidence: float
    raw: dict[str, Any]


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:40]


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object from a string."""
    text = text.strip()
    if not text:
        return None
    # Fast path
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # Best-effort: find the first {...} block
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _validate_choice(payload: dict[str, Any], candidates: list[str]) -> LlmChooseSkuResult | None:
    try:
        parsed = LlmParseResponse.model_validate(payload)
    except ValidationError:
        return None
    if parsed.match.sku_key not in set(candidates):
        return None
    return LlmChooseSkuResult(
        sku_key=parsed.match.sku_key,
        match_confidence=float(parsed.match.match_confidence),
        raw=payload,
    )


async def choose_sku_key_from_candidates(
    *,
    title: str,
    second_hand_condition: str | None,
    merchant_name: str | None,
    candidates: list[str],
) -> LlmChooseSkuResult | None:
    """Ask the LLM to choose the best sku_key from candidates for a raw title."""
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        return None
    if not title.strip():
        return None
    if not candidates:
        return None

    candidates = list(dict.fromkeys([c.strip() for c in candidates if c.strip()]))
    if not candidates:
        return None

    cond = (second_hand_condition or "").strip()
    merchant = (merchant_name or "").strip()
    candidates_fingerprint = _hash_key(*candidates)
    cache_key = f"{PREFIX_LLM_PARSE}{_hash_key(title, cond, merchant, candidates_fingerprint)}"

    cached = await cache_get(cache_key)
    if cached:
        payload = _extract_first_json_object(cached)
        if payload:
            res = _validate_choice(payload, candidates=candidates)
            if res:
                return res

    lock_key = f"{PREFIX_LLM_LOCK}{_hash_key(cache_key)}"
    got_lock = await acquire_lock(lock_key, ttl=TTL_LLM_LOCK)
    if not got_lock:
        # Another worker is computing; rely on cache next run.
        return None

    try:
        # Re-check cache after lock acquisition.
        cached2 = await cache_get(cache_key)
        if cached2:
            payload = _extract_first_json_object(cached2)
            if payload:
                res = _validate_choice(payload, candidates=candidates)
                if res:
                    return res

        system_prompt = (
            "You are a product-title parser for iPhone SKUs.\n"
            "Choose the single best sku_key from the provided candidates.\n"
            "Return ONLY valid JSON matching this shape:\n"
            '{ "is_accessory": bool, "is_bundle": bool, "is_contract": bool, '
            '"match": { "sku_key": string, "match_confidence": number, "reason": string|null } }\n'
            "Rules:\n"
            "- sku_key MUST be exactly one of the candidates\n"
            "- match_confidence is 0..1\n"
            "- Do not include any extra keys"
        )

        user_prompt = (
            f"title: {title}\n"
            f"second_hand_condition: {cond}\n"
            f"merchant: {merchant}\n"
            "candidates:\n"
            + "\n".join(f"- {c}" for c in candidates)
        )

        url = settings.openai_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
        body = {
            "model": settings.openai_model_parse,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_completion_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()

        # Extract from chat completions response: choices[0].message.content
        text_out = ""
        if isinstance(data, dict) and isinstance(data.get("choices"), list):
            for choice in data["choices"]:
                if isinstance(choice, dict):
                    msg = choice.get("message")
                    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                        text_out = msg["content"]
                        break

        payload = _extract_first_json_object(text_out) or {}
        # Cache raw for future runs (even if invalid; it may still be useful to inspect via DB raw attrs)
        await cache_set(cache_key, json.dumps(payload, ensure_ascii=False), TTL_LLM_PARSE)

        res = _validate_choice(payload, candidates=candidates)
        if res is None:
            logger.warning("LLM parse invalid or out-of-candidates")
        return res
    except httpx.HTTPStatusError as e:
        status = int(e.response.status_code) if e.response is not None else 0
        response_text = e.response.text[:500] if e.response is not None else ""
        logger.error(
            f"[llm_parser] OpenAI HTTP {status} url={url} model={settings.openai_model_parse} "
            f"response={response_text}"
        )
        return None
    except Exception:
        logger.exception("LLM parse failed")
        return None
    finally:
        await release_lock(lock_key)

