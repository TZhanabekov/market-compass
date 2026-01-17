"""Pattern matching helpers for contract/condition detection.

Goal:
- Keep default (hardcoded) rules for deterministic behavior.
- Allow admin-managed phrases in DB to extend/override without code deploys.

Important:
- Phrases are matched as literal substrings (lowercased), NOT regex.
- Match can consider both title and product_link for better recall.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pattern_phrase import PatternPhrase


KIND_CONTRACT = "contract"
KIND_CONDITION_NEW = "condition_new"
KIND_CONDITION_USED = "condition_used"
KIND_CONDITION_REFURBISHED = "condition_refurbished"


DEFAULT_CONTRACT_PHRASES: tuple[str, ...] = (
    # English
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
)


DEFAULT_CONDITION_USED_PHRASES: tuple[str, ...] = (
    "used",
    "pre-owned",
    "pre owned",
    "中古",
    "중고",
    "二手",
    "مستعمل",
    "gebraucht",
    "occasion",
)

DEFAULT_CONDITION_REFURBISHED_PHRASES: tuple[str, ...] = (
    "refurbished",
    "renewed",
    "reconditioned",
    "整備済み",
    "リファービッシュ",
    "리퍼",
    "翻新",
    "مجدد",
)

DEFAULT_CONDITION_NEW_PHRASES: tuple[str, ...] = (
    "brand new",
    "new",
    "新品",
    "새제품",
    "全新",
    "جديد",
    "neu",
    "neuf",
)


def _normalize_phrase(s: str) -> str:
    s = s.strip().lower()
    # Collapse whitespace to single spaces for stable matching
    s = re.sub(r"\s+", " ", s)
    return s


def _link_hint(product_link: str | None) -> str:
    if not product_link:
        return ""
    try:
        u = urlparse(product_link)
        # Keep host + path + query (query often contains useful tokens)
        hint = f"{u.hostname or ''}{u.path or ''}?{u.query or ''}"
        return hint.lower()
    except Exception:
        return str(product_link).lower()


def _haystack(title: str | None, product_link: str | None) -> str:
    t = (title or "").strip().lower()
    return f"{t}\n{_link_hint(product_link)}"


@dataclass(frozen=True)
class PatternBundle:
    contract: tuple[str, ...]
    condition_new: tuple[str, ...]
    condition_used: tuple[str, ...]
    condition_refurbished: tuple[str, ...]


async def load_pattern_bundle(session: AsyncSession) -> PatternBundle:
    """Load enabled admin-managed phrases and merge with defaults."""
    res = await session.execute(
        select(PatternPhrase).where(PatternPhrase.enabled.is_(True))
    )
    rows = res.scalars().all()

    by_kind: dict[str, list[str]] = {
        KIND_CONTRACT: [],
        KIND_CONDITION_NEW: [],
        KIND_CONDITION_USED: [],
        KIND_CONDITION_REFURBISHED: [],
    }
    for r in rows:
        k = str(r.kind or "").strip()
        if k not in by_kind:
            continue
        p = _normalize_phrase(str(r.phrase or ""))
        if p:
            by_kind[k].append(p)

    def _merge(defaults: Iterable[str], extras: list[str]) -> tuple[str, ...]:
        merged = [_normalize_phrase(x) for x in defaults]
        merged.extend(extras)
        # de-dup while preserving order
        out: list[str] = []
        seen: set[str] = set()
        for x in merged:
            if not x or x in seen:
                continue
            out.append(x)
            seen.add(x)
        return tuple(out)

    return PatternBundle(
        contract=_merge(DEFAULT_CONTRACT_PHRASES, by_kind[KIND_CONTRACT]),
        condition_new=_merge(DEFAULT_CONDITION_NEW_PHRASES, by_kind[KIND_CONDITION_NEW]),
        condition_used=_merge(DEFAULT_CONDITION_USED_PHRASES, by_kind[KIND_CONDITION_USED]),
        condition_refurbished=_merge(
            DEFAULT_CONDITION_REFURBISHED_PHRASES, by_kind[KIND_CONDITION_REFURBISHED]
        ),
    )


def detect_is_contract(*, title: str | None, product_link: str | None, patterns: PatternBundle) -> bool:
    hay = _haystack(title, product_link)
    return any(p in hay for p in patterns.contract)


def detect_condition_hint(
    *, title: str | None, product_link: str | None, patterns: PatternBundle
) -> tuple[str | None, list[str]]:
    """Return (condition|None, matched_phrases). Condition is one of: new/used/refurbished."""
    hay = _haystack(title, product_link)
    matched: list[str] = []

    # Priority: refurbished > used > new (safer)
    for p in patterns.condition_refurbished:
        if p in hay:
            matched.append(p)
    if matched:
        return "refurbished", matched[:5]

    for p in patterns.condition_used:
        if p in hay:
            matched.append(p)
    if matched:
        return "used", matched[:5]

    for p in patterns.condition_new:
        if p in hay:
            matched.append(p)
    if matched:
        return "new", matched[:5]

    return None, []

