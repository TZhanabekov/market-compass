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

import hashlib
import json
import logging
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
    sample_size: int
    suggestions: dict[str, list[SuggestionItem]]
    raw: dict[str, Any]


async def suggest_patterns(
    *,
    session: AsyncSession,
    sample_limit: int = 2000,
    llm_batches: int = 3,
    items_per_batch: int = 120,
) -> PatternSuggestResult:
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        raise RuntimeError("LLM is not enabled/configured")

    sample_limit = max(50, min(int(sample_limit), 5000))
    llm_batches = max(1, min(int(llm_batches), 10))
    items_per_batch = max(20, min(int(items_per_batch), 250))

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
            sample_size=0,
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
                sample_size=sample_size,
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
                    sample_size=sample_size,
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
                        "title": t[:160],
                        "link_hint": _url_hint(u),
                    }
                )
            if payload_chunk:
                batches.append(payload_chunk)

        merged = PatternSuggestResponse()
        raw_payloads: list[dict[str, Any]] = []

        for b in batches:
            llm_calls += 1
            p = await _call_llm_suggest(b)
            raw_payloads.append(p)
            try:
                parsed = PatternSuggestResponse.model_validate(p)
            except ValidationError:
                continue

            merged.contract.extend(parsed.contract)
            merged.condition_new.extend(parsed.condition_new)
            merged.condition_used.extend(parsed.condition_used)
            merged.condition_refurbished.extend(parsed.condition_refurbished)

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
        }
        payload["_raw_llm_payloads"] = raw_payloads[:5]

        await cache_set(cache_key, json.dumps(payload, ensure_ascii=False), TTL_SUGGEST_CACHE)

        suggestions = _score_suggestions(out, rows)
        return PatternSuggestResult(
            cached=False,
            llm_calls=llm_calls,
            sample_size=sample_size,
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
    settings = get_settings()
    prompt = (
        "You analyze iPhone shopping listings.\n"
        "Task: propose literal phrases (not regex) that help detect:\n"
        "- contract/plan listings (subscription/installments)\n"
        "- condition hints: new vs used vs refurbished\n\n"
        "You MUST use only phrases that appear in the provided inputs (title or link_hint).\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        '{ "contract": string[], "condition_new": string[], "condition_used": string[], "condition_refurbished": string[] }\n'
        "Rules:\n"
        "- lowercase phrases\n"
        "- phrases are 2..80 chars\n"
        "- no regex syntax, no wildcards\n"
        "- prefer multi-word phrases when possible\n\n"
        "inputs:\n"
        + "\n".join(f"- title: {x['title']}\n  link_hint: {x['link_hint']}" for x in items[:250])
    )

    url = settings.openai_base_url.rstrip("/") + "/responses"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    body = {"model": settings.openai_model_parse, "input": prompt}

    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    text_out = ""
    if isinstance(data, dict):
        if isinstance(data.get("output_text"), str):
            text_out = data["output_text"]
        elif isinstance(data.get("output"), list):
            chunks: list[str] = []
            for item in data["output"]:
                content = item.get("content") if isinstance(item, dict) else None
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and isinstance(c.get("text"), str):
                            chunks.append(c["text"])
            text_out = "\n".join(chunks)

    return _extract_first_json_object(text_out) or {}


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

