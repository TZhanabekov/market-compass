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
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawOffer
from app.models.pattern_suggestion import PatternSuggestion
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


class SuggestedPhrase(BaseModel):
    phrase: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("phrase")
    @classmethod
    def _norm_phrase(cls, v: str) -> str:
        return _normalize_phrase(str(v))


class PatternSuggestResponse(BaseModel):
    contract: list[SuggestedPhrase] = Field(default_factory=list)
    condition_new: list[SuggestedPhrase] = Field(default_factory=list)
    condition_used: list[SuggestedPhrase] = Field(default_factory=list)
    condition_refurbished: list[SuggestedPhrase] = Field(default_factory=list)


@dataclass(frozen=True)
class SuggestionItem:
    phrase: str
    match_count: int
    llm_confidence: float
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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def persist_pattern_suggestions(
    *,
    session: AsyncSession,
    run_id: str,
    sample_size: int,
    suggestions: dict[str, list[SuggestionItem]],
) -> None:
    """Upsert suggestions into DB for review in admin UI."""
    now = _now_utc()

    for kind, items in suggestions.items():
        for it in items:
            phrase = _normalize_phrase(it.phrase)
            if not phrase:
                continue
            conf = float(it.llm_confidence or 0.0)

            res = await session.execute(
                select(PatternSuggestion).where(
                    PatternSuggestion.kind == kind,
                    PatternSuggestion.phrase == phrase,
                )
            )
            row = res.scalar_one_or_none()

            examples_json = json.dumps(it.examples, ensure_ascii=False)
            if row:
                row.match_count_last = int(it.match_count)
                row.sample_size_last = int(sample_size)
                row.llm_confidence_last = conf
                row.match_count_max = max(int(row.match_count_max or 0), int(it.match_count))
                row.llm_confidence_max = max(float(row.llm_confidence_max or 0.0), conf)
                row.examples_json = examples_json
                row.last_run_id = run_id
                row.last_seen_at = now
            else:
                row = PatternSuggestion(
                    kind=kind,
                    phrase=phrase,
                    match_count_last=int(it.match_count),
                    sample_size_last=int(sample_size),
                    llm_confidence_last=conf,
                    match_count_max=int(it.match_count),
                    llm_confidence_max=conf,
                    examples_json=examples_json,
                    last_run_id=run_id,
                    last_seen_at=now,
                )
                session.add(row)


async def suggest_patterns(
    *,
    session: AsyncSession,
    sample_limit: int = 2000,
    llm_batches: int = 3,
    items_per_batch: int = 80,
    force_refresh: bool = False,
) -> PatternSuggestResult:
    settings = get_settings()
    if not settings.llm_enabled or not settings.openai_api_key:
        raise RuntimeError("LLM is not enabled/configured")

    # Hard caps to prevent oversized prompts/timeouts in production.
    sample_limit = max(50, min(int(sample_limit), 2000))
    llm_batches = max(1, min(int(llm_batches), 4))
    items_per_batch = max(20, min(int(items_per_batch), 80))
    max_concurrency = max(1, min(int(getattr(settings, "pattern_suggest_max_concurrency", 2)), 8))

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

    if not force_refresh:
        cached = await cache_get(cache_key)
        if cached:
            payload = _extract_first_json_object(cached)
            if isinstance(payload, dict):
                try:
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
                except ValidationError:
                    # Old cached schema or corrupted payload; ignore cache.
                    logger.info("[pattern_suggest] cached payload schema mismatch; ignoring cache")

    lock_key = f"{PREFIX_SUGGEST_LOCK}{_hash_key(cache_key)}"
    got_lock = await acquire_lock(lock_key, ttl=TTL_SUGGEST_LOCK)
    if not got_lock:
        raise RuntimeError("pattern_suggest is already running")

    llm_calls = 0
    try:
        # Re-check cache after lock
        if not force_refresh:
            cached2 = await cache_get(cache_key)
            if cached2:
                payload = _extract_first_json_object(cached2)
                if isinstance(payload, dict):
                    try:
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
                    except ValidationError:
                        logger.info("[pattern_suggest] cached payload schema mismatch; ignoring cache")

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

        # Run batches concurrently (bounded) to reduce wall time while respecting rate limits.
        sem = asyncio.Semaphore(max_concurrency)

        async def _run_batch(batch: list[dict[str, str]]) -> tuple[dict[str, Any], str | None]:
            async with sem:
                return await _call_llm_suggest(batch)

        llm_calls = len(batches)
        results = await asyncio.gather(*(_run_batch(b) for b in batches), return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res)[:200])
                continue
            try:
                p, request_id = res
                if len(raw_payloads) < 5:
                    raw_payloads.append({"openai_request_id": request_id, "payload": p})
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
            "cache_key": cache_key,
            "force_refresh": bool(force_refresh),
            "max_concurrency": max_concurrency,
        }
        payload["_raw_llm_payloads"] = raw_payloads[:5]

        # Log compact debug info for observability (avoid logging huge raw inputs).
        logger.info(
            "[pattern_suggest] done cached=%s force_refresh=%s sample=%s llm_calls=%s ok=%s errors=%s cache_key=%s",
            False,
            bool(force_refresh),
            sample_size,
            llm_calls,
            ok_calls,
            len(errors),
            cache_key,
        )
        if raw_payloads:
            logger.info(
                "[pattern_suggest] openai_request_ids=%s",
                [x.get("openai_request_id") for x in raw_payloads if isinstance(x, dict)],
            )

        await cache_set(cache_key, json.dumps(payload, ensure_ascii=False), TTL_SUGGEST_CACHE)

        suggestions = _score_suggestions(out, rows)

        # Persist suggestions for later review in Admin UI.
        run_id = uuid4().hex[:20]
        try:
            await persist_pattern_suggestions(
                session=session,
                run_id=run_id,
                sample_size=sample_size,
                suggestions=suggestions,
            )
        except Exception:
            logger.exception("[pattern_suggest] failed to persist suggestions")

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


async def _call_llm_suggest(items: list[dict[str, str]]) -> tuple[dict[str, Any], str | None]:
    settings = get_settings()
    system_prompt = (
        "You analyze iPhone shopping listings.\n"
        "Task: propose literal phrases (not regex) that help detect:\n"
        "- contract/plan listings (subscription/installments)\n"
        "- condition hints: new vs used vs refurbished\n\n"
        "You MUST use only phrases that appear in the provided inputs (title or link_hint).\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        '{ "contract": {"phrase": string, "confidence": number}[], '
        '"condition_new": {"phrase": string, "confidence": number}[], '
        '"condition_used": {"phrase": string, "confidence": number}[], '
        '"condition_refurbished": {"phrase": string, "confidence": number}[] }\n'
        "Rules:\n"
        "- lowercase phrases\n"
        "- phrases are 2..80 chars\n"
        "- no regex syntax, no wildcards\n"
        "- prefer multi-word phrases when possible\n"
        "- confidence is 0..1, higher = more sure the phrase indicates that category"
    )

    user_prompt = (
        "inputs:\n"
        + "\n".join(f"- title: {x['title']}\n  link_hint: {x['link_hint']}" for x in items[:250])
    )

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    body = {
        "model": settings.openai_model_parse,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # GPT-5: completion tokens include reasoning+output; keep enough room.
        "max_completion_tokens": 3000,
        # GPT-5: reduce hidden reasoning to avoid empty content.
        "reasoning_effort": "minimal",
        # GPT-5 class models: enforce JSON object output when supported.
        "response_format": {"type": "json_object"},
    }

    # Log what we send (truncated) for debugging.
    logger.info(
        "[pattern_suggest] sending model=%s host=%s batch_items=%s prompt_preview=%s",
        settings.openai_model_parse,
        urlparse(settings.openai_base_url).hostname if settings.openai_base_url else None,
        len(items),
        (system_prompt + "\n\n" + user_prompt)[:800],
    )

    # Retry transient upstream failures (502/503/504/429).
    waits = [0.0, 1.0, 2.0, 4.0]
    last_err: str | None = None
    data: dict[str, Any] | None = None
    request_id: str | None = None

    for attempt, wait_s in enumerate(waits, 1):
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(url, headers=headers, json=body)
                r.raise_for_status()
                request_id = r.headers.get("x-request-id")
                # Log actual rate-limit headers so we can tune concurrency safely.
                rl = {
                    "limit_requests": r.headers.get("x-ratelimit-limit-requests"),
                    "remaining_requests": r.headers.get("x-ratelimit-remaining-requests"),
                    "reset_requests": r.headers.get("x-ratelimit-reset-requests"),
                    "limit_tokens": r.headers.get("x-ratelimit-limit-tokens"),
                    "remaining_tokens": r.headers.get("x-ratelimit-remaining-tokens"),
                    "reset_tokens": r.headers.get("x-ratelimit-reset-tokens"),
                }
                logger.info("[pattern_suggest] openai_ratelimit=%s request_id=%s", rl, request_id)
                data_raw = r.json()
                data = data_raw if isinstance(data_raw, dict) else {}
                last_err = None
                break
        except httpx.TimeoutException:
            last_err = "LLM request timed out"
            logger.warning(f"[pattern_suggest] LLM timeout attempt={attempt}/{len(waits)}")
        except httpx.HTTPStatusError as e:
            status = int(e.response.status_code) if e.response is not None else 0
            response_text = e.response.text[:500] if e.response is not None else ""
            if e.response is not None and status in (429, 500, 502, 503, 504):
                logger.warning(
                    "[pattern_suggest] openai_ratelimit_headers=%s",
                    {
                        "x-ratelimit-limit-requests": e.response.headers.get("x-ratelimit-limit-requests"),
                        "x-ratelimit-remaining-requests": e.response.headers.get("x-ratelimit-remaining-requests"),
                        "x-ratelimit-reset-requests": e.response.headers.get("x-ratelimit-reset-requests"),
                        "x-ratelimit-limit-tokens": e.response.headers.get("x-ratelimit-limit-tokens"),
                        "x-ratelimit-remaining-tokens": e.response.headers.get("x-ratelimit-remaining-tokens"),
                        "x-ratelimit-reset-tokens": e.response.headers.get("x-ratelimit-reset-tokens"),
                    },
                )
            logger.warning(
                f"[pattern_suggest] LLM HTTP {status} attempt={attempt}/{len(waits)} "
                f"url={url} model={settings.openai_model_parse} response={response_text}"
            )
            # 400 = invalid request (e.g. bad model/param) - don't retry
            if status == 400:
                raise RuntimeError(f"LLM invalid request (HTTP 400): {response_text[:200]}") from e
            # Retry transient errors
            if status in (429, 500, 502, 503, 504):
                last_err = f"LLM upstream HTTP {status}"
                continue
            raise RuntimeError(f"LLM upstream HTTP {status}: {response_text[:200]}") from e
        except Exception as e:
            last_err = f"LLM request failed: {type(e).__name__}"
            logger.exception(f"[pattern_suggest] LLM unexpected error attempt={attempt}/{len(waits)}")

    if data is None:
        raise RuntimeError(last_err or "LLM request failed")

    # Extract from chat completions response.
    # Depending on model/SDK, message.content can be a string OR a list of content parts.
    text_out = ""
    first_choice: dict[str, Any] | None = None
    if isinstance(data.get("choices"), list) and data["choices"]:
        c0 = data["choices"][0]
        if isinstance(c0, dict):
            first_choice = c0

    if isinstance(data.get("choices"), list):
        for choice in data["choices"]:
            if not isinstance(choice, dict):
                continue
            msg = choice.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                text_out = content
                break
            if isinstance(content, list):
                parts: list[str] = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                if parts:
                    text_out = "\n".join(parts)
                    break

    logger.info(
        "[pattern_suggest] received request_id=%s finish_reason=%s response_preview=%s",
        request_id,
        first_choice.get("finish_reason") if isinstance(first_choice, dict) else None,
        (text_out or "")[:800],
    )
    if not text_out and first_choice is not None:
        logger.info("[pattern_suggest] first_choice_preview=%s", json.dumps(first_choice)[:800])
        # Treat empty content as an error so the caller can retry / adjust params.
        raise RuntimeError("LLM returned empty content (likely all tokens spent on reasoning)")

    return _extract_first_json_object(text_out) or {}, request_id


def _score_suggestions(parsed: PatternSuggestResponse, rows: list[tuple[str, str]]) -> dict[str, list[SuggestionItem]]:
    haystacks = [(t.lower(), u.lower()) for (t, u) in rows]

    def _score(items: list[SuggestedPhrase]) -> list[SuggestionItem]:
        out: list[SuggestionItem] = []
        # De-dup by phrase; keep max confidence if repeated across batches.
        conf_by_phrase: dict[str, float] = {}
        for it in items:
            p = _normalize_phrase(it.phrase)
            if not p:
                continue
            conf_by_phrase[p] = max(float(conf_by_phrase.get(p, 0.0)), float(it.confidence))

        for p in _dedup_norm(list(conf_by_phrase.keys()), limit=50):
            c = 0
            examples: list[dict[str, str]] = []
            for t, u in haystacks:
                if p in t or p in u:
                    c += 1
                    if len(examples) < 3:
                        examples.append({"title": t[:180], "link": u[:220]})
            if c > 0:
                out.append(
                    SuggestionItem(
                        phrase=p,
                        match_count=c,
                        llm_confidence=float(conf_by_phrase.get(p, 0.0)),
                        examples=examples,
                    )
                )
        out.sort(key=lambda x: x.match_count, reverse=True)
        return out[:25]

    return {
        KIND_CONTRACT: _score(parsed.contract),
        KIND_CONDITION_NEW: _score(parsed.condition_new),
        KIND_CONDITION_USED: _score(parsed.condition_used),
        KIND_CONDITION_REFURBISHED: _score(parsed.condition_refurbished),
    }

