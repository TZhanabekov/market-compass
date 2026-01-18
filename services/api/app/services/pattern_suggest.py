"""LLM-assisted suggestion of pattern phrases for contract/condition detection.

This is an admin-only tool:
- Reads a sample of recent raw_offers (title + product_link)
- Calls LLM in batches to propose phrases to add
- Returns suggestions + simple match analytics (count + examples)

Safety:
- No regex suggestions; only literal phrases.
- Output is strict JSON; validated server-side.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawOffer
from app.settings import get_settings
from app.stores.redis import acquire_lock, cache_get, cache_set, release_lock
from app.services.patterns import (
    KIND_CONDITION_NEW,
    KIND_CONDITION_REFURBISHED,
    KIND_CONDITION_USED,
    KIND_CONTRACT,
)

logger = logging.getLogger("uvicorn.error")

TTL_SUGGEST_CACHE = 24 * 3600
TTL_SUGGEST_LOCK = 5 * 60
PREFIX_SUGGEST_CACHE = "llm:patterns:suggest:"
PREFIX_SUGGEST_LOCK = "llm:patterns:suggest:"


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:40]


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _url_hint(url: str) -> str:
    try:
        u = urlparse(url)
        host = u.hostname or ""
        path = u.path or ""
        query = u.query or ""
        s = f"{host}{path}?{query}".strip("?")
        return s[:200]
    except Exception:
        return str(url)[:200]


def _normalize_phrase(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


class PatternSuggestResponse(BaseModel):
    contract: list[str] = Field(default_factory=list)
    condition_new: list[str] = Field(default_factory=list)
    condition_used: list[str] = Field(default_factory=list)
    condition_refurbished: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class SuggestionItem:
    phrase: str
    match_count: int
    examples: list[dict[str, str]]


@dataclass(frozen=True)
class PatternSuggestResult:
    cached: bool
    llm_calls: int
    llm_successful_calls: int
    sample_size: int
    errors: list[str]
    suggestions: dict[str, list[SuggestionItem]]
    raw: dict[str, Any]


async def suggest_patterns(
    *,
    session: AsyncSession,
    sample_limit: int = 2000,
    llm_batches: int = 3,
    items_per_batch: int = 80,
) -> PatternSuggestResult:
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        raise RuntimeError("LLM is not enabled/configured")

    # Hard caps to prevent oversized prompts/timeouts in production.
    sample_limit = max(50, min(int(sample_limit), 2000))
    llm_batches = max(1, min(int(llm_batches), 4))
    items_per_batch = max(20, min(int(items_per_batch), 80))

    # Sample last N raw_offers (recent)
    res = await session.execute(
        select(RawOffer.title_raw, RawOffer.product_link)
        .order_by(RawOffer.ingested_at.desc())
        .limit(sample_limit)
    )
    rows = [(str(t or ""), str(u or "")) for (t, u) in res.all()]
    sample_size = len(rows)
    if sample_size == 0:
        return PatternSuggestResult(
            cached=False,
            llm_calls=0,
            llm_successful_calls=0,
            sample_size=0,
            errors=[],
            suggestions={},
            raw={"ok": True, "empty": True},
        )

    # Cache key from a small fingerprint of sample
    fp_parts = []
    for t, u in rows[:100]:
        fp_parts.append(t[:80])
        fp_parts.append(u[:80])
    cache_key = f"{PREFIX_SUGGEST_CACHE}{_hash_key(str(sample_size), *fp_parts)}"

    cached = await cache_get(cache_key)
    if cached:
        payload = _extract_first_json_object(cached)
        if isinstance(payload, dict):
            parsed = PatternSuggestResponse.model_validate(payload)
            suggestions = _score_suggestions(parsed, rows)
            return PatternSuggestResult(
                cached=True,
                llm_calls=0,
                llm_successful_calls=0,
                sample_size=sample_size,
                errors=[],
                suggestions=suggestions,
                raw=payload,
            )

    lock_key = f"{PREFIX_SUGGEST_LOCK}{_hash_key(cache_key)}"
    got_lock = await acquire_lock(lock_key, ttl=TTL_SUGGEST_LOCK)
    if not got_lock:
        raise RuntimeError("pattern_suggest is already running")

    llm_calls = 0
    try:
        # Re-check cache after lock
        cached2 = await cache_get(cache_key)
        if cached2:
            payload = _extract_first_json_object(cached2)
            if isinstance(payload, dict):
                parsed = PatternSuggestResponse.model_validate(payload)
                suggestions = _score_suggestions(parsed, rows)
                return PatternSuggestResult(
                    cached=True,
                    llm_calls=0,
                    llm_successful_calls=0,
                    sample_size=sample_size,
                    errors=[],
                    suggestions=suggestions,
                    raw=payload,
                )

        # Build representative batches (evenly spaced)
        batches: list[list[dict[str, str]]] = []
        for i in range(llm_batches):
            start = int(i * sample_size / llm_batches)
            end = min(sample_size, start + items_per_batch)
            chunk = rows[start:end]
            payload_chunk: list[dict[str, str]] = []
            for t, u in chunk:
                if not t.strip():
                    continue
                payload_chunk.append(
                    {
                        "title": t[:120],
                        "link_hint": _url_hint(u)[:120],
                    }
                )
            if payload_chunk:
                batches.append(payload_chunk)

        merged = PatternSuggestResponse()
        raw_payloads: list[dict[str, Any]] = []
        errors: list[str] = []
        ok_calls = 0

        for b in batches:
            llm_calls += 1
            try:
                p = await _call_llm_suggest(b)
                raw_payloads.append(p)
                parsed = PatternSuggestResponse.model_validate(p)
                ok_calls += 1
            except (RuntimeError, ValidationError) as e:
                errors.append(str(e)[:200])
                continue

            merged.contract.extend(parsed.contract)
            merged.condition_new.extend(parsed.condition_new)
            merged.condition_used.extend(parsed.condition_used)
            merged.condition_refurbished.extend(parsed.condition_refurbished)

        if ok_calls == 0:
            raise RuntimeError("LLM upstream error (all batches failed)")

        # normalize + de-dup, keep short lists
        out = PatternSuggestResponse(
            contract=_dedup_norm(merged.contract, limit=30),
            condition_new=_dedup_norm(merged.condition_new, limit=30),
            condition_used=_dedup_norm(merged.condition_used, limit=30),
            condition_refurbished=_dedup_norm(merged.condition_refurbished, limit=30),
        )

        payload = out.model_dump()
        payload["_meta"] = {
            "sample_size": sample_size,
            "llm_calls": llm_calls,
            "llm_successful_calls": ok_calls,
            "errors": errors,
        }
        payload["_raw_llm_payloads"] = raw_payloads[:5]

        await cache_set(cache_key, json.dumps(payload, ensure_ascii=False), TTL_SUGGEST_CACHE)

        suggestions = _score_suggestions(out, rows)
        return PatternSuggestResult(
            cached=False,
            llm_calls=llm_calls,
            llm_successful_calls=ok_calls,
            sample_size=sample_size,
            errors=errors,
            suggestions=suggestions,
            raw=payload,
        )
    finally:
        await release_lock(lock_key)


def _dedup_norm(items: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        p = _normalize_phrase(str(x))
        if not p or len(p) < 2:
            continue
        if len(p) > 80:
            continue
        if p in seen:
            continue
        out.append(p)
        seen.add(p)
        if len(out) >= limit:
            break
    return out


async def _call_llm_suggest(items: list[dict[str, str]]) -> dict[str, Any]:
    """Call OpenAI Responses API with structured JSON output for pattern suggestions."""
    settings = get_settings()
    
    # Limit items to prevent oversized prompts (max ~50 items per batch)
    items = items[:50]
    
    # Build compact prompt
    inputs_text = "\n".join(
        f"{i+1}. title: {x['title'][:100]} | link: {x['link_hint'][:80]}"
        for i, x in enumerate(items)
    )
    
    prompt = (
        "Analyze iPhone shopping listings and propose literal phrases (not regex) to detect:\n"
        "- contract/plan (subscription/installments)\n"
        "- condition: new vs used vs refurbished\n\n"
        "Rules:\n"
        "- Use ONLY phrases that appear in the inputs below\n"
        "- lowercase, 2-80 chars, no regex/wildcards\n"
        "- Prefer multi-word phrases\n\n"
        f"Inputs:\n{inputs_text}\n\n"
        "Return valid JSON with keys: contract, condition_new, condition_used, condition_refurbished (each is string[])."
    )

    url = settings.openai_base_url.rstrip("/") + "/responses"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    
    # Use structured output (JSON mode) to force valid JSON
    body = {
        "model": settings.openai_model_parse,
        "input": prompt,
        "text": {
            "type": "json",
            "schema": {
                "type": "object",
                "properties": {
                    "contract": {"type": "array", "items": {"type": "string"}},
                    "condition_new": {"type": "array", "items": {"type": "string"}},
                    "condition_used": {"type": "array", "items": {"type": "string"}},
                    "condition_refurbished": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["contract", "condition_new", "condition_used", "condition_refurbished"],
            },
        },
    }

    # Exponential backoff with jitter for retries
    max_retries = 4
    base_delay = 1.0
    last_err: str | None = None
    data: dict[str, Any] | None = None

    for attempt in range(max_retries):
        if attempt > 0:
            # Exponential backoff: 1s, 2s, 4s, 8s + jitter
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
        
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data_raw = r.json()
                data = data_raw if isinstance(data_raw, dict) else {}
                last_err = None
                break
        except httpx.TimeoutException:
            last_err = "LLM request timed out"
            if attempt == max_retries - 1:
                break
        except httpx.HTTPStatusError as e:
            status = int(e.response.status_code) if e.response is not None else 0
            if status in (429, 500, 502, 503, 504):
                last_err = f"LLM upstream HTTP {status}"
                # For 429, wait longer before retry
                if status == 429 and attempt < max_retries - 1:
                    await asyncio.sleep(5.0 + random.uniform(0, 2.0))
                continue
            raise RuntimeError(f"LLM upstream HTTP {status}") from e
        except Exception as e:
            last_err = f"LLM request failed: {type(e).__name__}: {str(e)[:100]}"
            if attempt == max_retries - 1:
                break

    if data is None:
        raise RuntimeError(last_err or "LLM request failed")

    # Extract JSON from response (structured output should return JSON directly)
    text_out = ""
    
    # Try multiple response shapes (Responses API can vary)
    if isinstance(data.get("output_text"), str):
        text_out = str(data["output_text"])
    elif isinstance(data.get("output"), list):
        # output: [{content: [{type: "output_text", text: "..."}]}]
        chunks: list[str] = []
        for item in data["output"]:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict):
                            # Try "text" field
                            if isinstance(c.get("text"), str):
                                chunks.append(c["text"])
                            # Try "output_text" field
                            elif isinstance(c.get("output_text"), str):
                                chunks.append(c["output_text"])
        text_out = "\n".join(chunks)
    elif isinstance(data.get("choices"), list):
        # Fallback: chat-completions-like structure
        for choice in data["choices"]:
            if isinstance(choice, dict):
                msg = choice.get("message") or choice.get("text")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    text_out = msg["content"]
                    break
                elif isinstance(msg, str):
                    text_out = msg
                    break

    # Parse JSON (structured output should return valid JSON)
    if text_out.strip():
        parsed = _extract_first_json_object(text_out)
        if parsed:
            return parsed
    
    # If structured output worked, data might have the JSON directly
    if isinstance(data, dict):
        # Check if response already has our schema keys
        if all(k in data for k in ["contract", "condition_new", "condition_used", "condition_refurbished"]):
            return data
    
    logger.warning(f"Could not extract JSON from LLM response: {data.keys() if isinstance(data, dict) else type(data)}")
    return {}


def _score_suggestions(parsed: PatternSuggestResponse, rows: list[tuple[str, str]]) -> dict[str, list[SuggestionItem]]:
    haystacks = [(t.lower(), u.lower()) for (t, u) in rows]

    def _score(phrases: list[str]) -> list[SuggestionItem]:
        out: list[SuggestionItem] = []
        for p in _dedup_norm(phrases, limit=50):
            c = 0
            examples: list[dict[str, str]] = []
            for t, u in haystacks:
                if p in t or p in u:
                    c += 1
                    if len(examples) < 3:
                        examples.append({"title": t[:180], "link": u[:220]})
            if c > 0:
                out.append(SuggestionItem(phrase=p, match_count=c, examples=examples))
        out.sort(key=lambda x: x.match_count, reverse=True)
        return out[:25]

    return {
        KIND_CONTRACT: _score(parsed.contract),
        KIND_CONDITION_NEW: _score(parsed.condition_new),
        KIND_CONDITION_USED: _score(parsed.condition_used),
        KIND_CONDITION_REFURBISHED: _score(parsed.condition_refurbished),
    }

