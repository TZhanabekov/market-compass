"""Attribute extraction from product titles for Golden SKU matching.

Priority order (per docs/08-ranking-and-dedup.md):
1. Deterministic extraction from structured sources (when present)
2. Regex extraction from title/snippet
3. Controlled LLM fallback only if confidence is low (not implemented here)

Extracts:
- model (iPhone 16 Pro, iPhone 16 Pro Max, etc.)
- storage (128GB, 256GB, 512GB, 1TB)
- color (Black, White, Natural Titanium, etc.)
- condition (New, Refurbished, Used)
"""

import re
from dataclasses import dataclass
from enum import Enum

from app.services.dedup import SkuAttributes, normalize_color, normalize_storage


class ExtractionConfidence(Enum):
    """Confidence level for attribute extraction."""

    HIGH = "high"  # All required fields extracted with high certainty
    MEDIUM = "medium"  # Some fields missing or uncertain
    LOW = "low"  # Too many missing fields, may need LLM fallback


@dataclass
class ExtractionResult:
    """Result of attribute extraction from a product title."""

    attributes: SkuAttributes
    confidence: ExtractionConfidence
    raw_title: str
    matched_model: str | None = None
    matched_storage: str | None = None
    matched_color: str | None = None
    matched_condition: str | None = None


# ============================================================
# iPhone Model Patterns
# ============================================================

# Model patterns (order matters - more specific first)
_MODEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # iPhone 17 series (2025)
    (re.compile(r"iphone\s*17\s*pro\s*max", re.IGNORECASE), "iphone-17-pro-max"),
    (re.compile(r"iphone\s*17\s*pro(?!\s*max)", re.IGNORECASE), "iphone-17-pro"),
    (re.compile(r"iphone\s*17\s*air", re.IGNORECASE), "iphone-17-air"),  # New slim model, replaces Plus
    (re.compile(r"iphone\s*17(?!\s*pro|\s*air)", re.IGNORECASE), "iphone-17"),
    # iPhone 16 series (2024)
    (re.compile(r"iphone\s*16\s*pro\s*max", re.IGNORECASE), "iphone-16-pro-max"),
    (re.compile(r"iphone\s*16\s*pro(?!\s*max)", re.IGNORECASE), "iphone-16-pro"),
    (re.compile(r"iphone\s*16\s*plus", re.IGNORECASE), "iphone-16-plus"),
    (re.compile(r"iphone\s*16\s*e\b", re.IGNORECASE), "iphone-16e"),  # Budget model
    (re.compile(r"iphone\s*16e\b", re.IGNORECASE), "iphone-16e"),  # Alternative spelling
    (re.compile(r"iphone\s*16(?!\s*pro|\s*plus|\s*e)", re.IGNORECASE), "iphone-16"),
    # iPhone 15 series
    (re.compile(r"iphone\s*15\s*pro\s*max", re.IGNORECASE), "iphone-15-pro-max"),
    (re.compile(r"iphone\s*15\s*pro(?!\s*max)", re.IGNORECASE), "iphone-15-pro"),
    (re.compile(r"iphone\s*15\s*plus", re.IGNORECASE), "iphone-15-plus"),
    (re.compile(r"iphone\s*15(?!\s*pro|\s*plus)", re.IGNORECASE), "iphone-15"),
    # iPhone 14 series
    (re.compile(r"iphone\s*14\s*pro\s*max", re.IGNORECASE), "iphone-14-pro-max"),
    (re.compile(r"iphone\s*14\s*pro(?!\s*max)", re.IGNORECASE), "iphone-14-pro"),
    (re.compile(r"iphone\s*14\s*plus", re.IGNORECASE), "iphone-14-plus"),
    (re.compile(r"iphone\s*14(?!\s*pro|\s*plus)", re.IGNORECASE), "iphone-14"),
    # iPhone 13 series (still popular)
    (re.compile(r"iphone\s*13\s*pro\s*max", re.IGNORECASE), "iphone-13-pro-max"),
    (re.compile(r"iphone\s*13\s*pro(?!\s*max)", re.IGNORECASE), "iphone-13-pro"),
    (re.compile(r"iphone\s*13\s*mini", re.IGNORECASE), "iphone-13-mini"),
    (re.compile(r"iphone\s*13(?!\s*pro|\s*mini)", re.IGNORECASE), "iphone-13"),
    # iPhone SE series (order matters - specific patterns before generic)
    (re.compile(r"iphone\s*se\s*2022", re.IGNORECASE), "iphone-se-3"),  # SE 2022 = 3rd gen
    (re.compile(r"iphone\s*se\s*2020", re.IGNORECASE), "iphone-se-2"),  # SE 2020 = 2nd gen
    (re.compile(r"iphone\s*se\s*\(?3(rd)?\s*(gen(eration)?)?\)?", re.IGNORECASE), "iphone-se-3"),
    (re.compile(r"iphone\s*se\s*\(?2(nd)?\s*(gen(eration)?)?\)?", re.IGNORECASE), "iphone-se-2"),
    (re.compile(r"iphone\s*se\b", re.IGNORECASE), "iphone-se"),  # Generic SE (matches "iPhone SE 64GB")
]

# ============================================================
# Storage Patterns
# ============================================================

_STORAGE_PATTERN = re.compile(
    r"(\d+)\s*(gb|tb)",
    re.IGNORECASE,
)

# Valid iPhone storage options (for validation)
_VALID_STORAGES = {"64gb", "128gb", "256gb", "512gb", "1tb", "2tb"}


# ============================================================
# Color Patterns
# ============================================================

# Color patterns with normalized output
_COLOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Titanium colors (iPhone 15 Pro / 16 Pro)
    (re.compile(r"natural\s*titanium", re.IGNORECASE), "natural"),
    (re.compile(r"white\s*titanium", re.IGNORECASE), "white"),
    (re.compile(r"black\s*titanium", re.IGNORECASE), "black"),
    (re.compile(r"blue\s*titanium", re.IGNORECASE), "blue"),
    (re.compile(r"desert\s*titanium", re.IGNORECASE), "desert"),
    # iPhone 17 (standard) colors (2025)
    (re.compile(r"\bmist\s*blue\b", re.IGNORECASE), "mist-blue"),
    (re.compile(r"\bsage\b", re.IGNORECASE), "sage"),
    (re.compile(r"\blavender\b", re.IGNORECASE), "lavender"),
    # iPhone 17 Air colors (2025)
    (re.compile(r"\bsky\s*blue\b", re.IGNORECASE), "sky-blue"),
    (re.compile(r"\bcloud\s*white\b", re.IGNORECASE), "cloud-white"),
    (re.compile(r"\blight\s*gold\b", re.IGNORECASE), "light-gold"),
    (re.compile(r"\bspace\s*black\b", re.IGNORECASE), "space-black"),
    # iPhone 17 Pro colors (2025)
    (re.compile(r"deep\s*blue", re.IGNORECASE), "deep-blue"),
    (re.compile(r"cosmic\s*orange", re.IGNORECASE), "cosmic-orange"),
    # iPhone 16 colors (2024)
    (re.compile(r"\bultramarine\b", re.IGNORECASE), "ultramarine"),
    (re.compile(r"\bteal\b", re.IGNORECASE), "teal"),
    # Space colors (generic)
    (re.compile(r"space\s*gr[ae]y", re.IGNORECASE), "gray"),
    # Midnight / Starlight (iPhone 13/14/SE)
    (re.compile(r"\bmidnight\b", re.IGNORECASE), "midnight"),
    (re.compile(r"\bstarlight\b", re.IGNORECASE), "starlight"),
    # Basic colors
    (re.compile(r"\b(black|noir)\b", re.IGNORECASE), "black"),
    (re.compile(r"\b(white|blanc)\b", re.IGNORECASE), "white"),
    (re.compile(r"\b(blue|bleu)\b", re.IGNORECASE), "blue"),
    (re.compile(r"\b(pink|rose)\b", re.IGNORECASE), "pink"),
    (re.compile(r"\b(gold|or)\b", re.IGNORECASE), "gold"),
    (re.compile(r"\b(silver|argent)\b", re.IGNORECASE), "silver"),
    (re.compile(r"\b(purple|violet)\b", re.IGNORECASE), "purple"),
    (re.compile(r"\b(green|vert)\b", re.IGNORECASE), "green"),
    (re.compile(r"\b(yellow|jaune)\b", re.IGNORECASE), "yellow"),
    (re.compile(r"\b(red|rouge)\b", re.IGNORECASE), "red"),
    (re.compile(r"\b(orange)\b", re.IGNORECASE), "orange"),
    (re.compile(r"\bnatural\b", re.IGNORECASE), "natural"),
    (re.compile(r"\bdesert\b", re.IGNORECASE), "desert"),
    # German
    (re.compile(r"\bschwarz\b", re.IGNORECASE), "black"),
    (re.compile(r"\bwei(?:ß|ss)\b", re.IGNORECASE), "white"),
    (re.compile(r"\bblau\b", re.IGNORECASE), "blue"),
    (re.compile(r"\brosa\b", re.IGNORECASE), "pink"),
    (re.compile(r"\bgrün\b", re.IGNORECASE), "green"),
    (re.compile(r"\bgelb\b", re.IGNORECASE), "yellow"),
    (re.compile(r"\brot\b", re.IGNORECASE), "red"),
    (re.compile(r"\bsilber\b", re.IGNORECASE), "silver"),
    (re.compile(r"\bgold\b", re.IGNORECASE), "gold"),
    (re.compile(r"\blila\b", re.IGNORECASE), "purple"),
    # Japanese (colors / titanium)
    (re.compile(r"ディープ\s*ブルー", re.IGNORECASE), "deep-blue"),
    (re.compile(r"コズミック\s*オレンジ", re.IGNORECASE), "cosmic-orange"),
    (re.compile(r"スペース\s*ブラック", re.IGNORECASE), "space-black"),
    (re.compile(r"ブラック", re.IGNORECASE), "black"),
    (re.compile(r"ホワイト", re.IGNORECASE), "white"),
    (re.compile(r"ブルー", re.IGNORECASE), "blue"),
    (re.compile(r"ピンク", re.IGNORECASE), "pink"),
    (re.compile(r"グリーン", re.IGNORECASE), "green"),
    (re.compile(r"イエロー", re.IGNORECASE), "yellow"),
    (re.compile(r"レッド", re.IGNORECASE), "red"),
    (re.compile(r"パープル", re.IGNORECASE), "purple"),
    (re.compile(r"シルバー", re.IGNORECASE), "silver"),
    (re.compile(r"ゴールド", re.IGNORECASE), "gold"),
    (re.compile(r"ナチュラル\s*チタニウム|ナチュラルチタニウム", re.IGNORECASE), "natural"),
    (re.compile(r"デザート\s*チタニウム|デザートチタニウム", re.IGNORECASE), "desert"),
    # Korean (KR)
    (re.compile(r"딥\s*블루|딥블루", re.IGNORECASE), "deep-blue"),
    (re.compile(r"코스믹\s*오렌지|코즈믹\s*오렌지", re.IGNORECASE), "cosmic-orange"),
    (re.compile(r"블랙", re.IGNORECASE), "black"),
    (re.compile(r"화이트", re.IGNORECASE), "white"),
    (re.compile(r"블루", re.IGNORECASE), "blue"),
    (re.compile(r"그린", re.IGNORECASE), "green"),
    (re.compile(r"핑크", re.IGNORECASE), "pink"),
    (re.compile(r"옐로", re.IGNORECASE), "yellow"),
    (re.compile(r"레드", re.IGNORECASE), "red"),
    (re.compile(r"퍼플", re.IGNORECASE), "purple"),
    (re.compile(r"실버", re.IGNORECASE), "silver"),
    (re.compile(r"골드", re.IGNORECASE), "gold"),
    # Chinese (HK/SG) - prefer explicit color words to reduce false positives
    (re.compile(r"深[藍蓝]", re.IGNORECASE), "deep-blue"),
    (re.compile(r"黑色", re.IGNORECASE), "black"),
    (re.compile(r"白色", re.IGNORECASE), "white"),
    (re.compile(r"(?:藍色|蓝色)", re.IGNORECASE), "blue"),
    (re.compile(r"(?:綠色|绿色)", re.IGNORECASE), "green"),
    (re.compile(r"粉紅|粉红|粉色", re.IGNORECASE), "pink"),
    (re.compile(r"(?:黃色|黄色)", re.IGNORECASE), "yellow"),
    (re.compile(r"(?:紅色|红色)", re.IGNORECASE), "red"),
    (re.compile(r"紫色", re.IGNORECASE), "purple"),
    (re.compile(r"(?:銀色|银色)", re.IGNORECASE), "silver"),
    (re.compile(r"金色", re.IGNORECASE), "gold"),
    # Arabic (AE)
    (re.compile(r"أسود", re.IGNORECASE), "black"),
    (re.compile(r"أبيض", re.IGNORECASE), "white"),
    (re.compile(r"أزرق", re.IGNORECASE), "blue"),
    (re.compile(r"أخضر", re.IGNORECASE), "green"),
    (re.compile(r"وردي", re.IGNORECASE), "pink"),
    (re.compile(r"أصفر", re.IGNORECASE), "yellow"),
    (re.compile(r"أحمر", re.IGNORECASE), "red"),
    (re.compile(r"بنفسجي", re.IGNORECASE), "purple"),
    (re.compile(r"فضي", re.IGNORECASE), "silver"),
    (re.compile(r"ذهبي", re.IGNORECASE), "gold"),
    # Product RED
    (re.compile(r"\(product\)\s*red", re.IGNORECASE), "red"),
    (re.compile(r"product\s*red", re.IGNORECASE), "red"),
]


# ============================================================
# Condition Patterns
# ============================================================

_CONDITION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(refurbished|refurb|renewed|certified\s*pre-?owned)\b", re.IGNORECASE), "refurbished"),
    (re.compile(r"\b(used|pre-?owned|second\s*hand)\b", re.IGNORECASE), "used"),
    (re.compile(r"\b(new|brand\s*new|sealed|bnib)\b", re.IGNORECASE), "new"),
    # German
    (re.compile(r"\b(generalüberholt|generalueberholt)\b", re.IGNORECASE), "refurbished"),
    (re.compile(r"\bgebraucht\b", re.IGNORECASE), "used"),
    (re.compile(r"\bneu\b", re.IGNORECASE), "new"),
    # French
    (re.compile(r"\breconditionn(?:é|e)\b", re.IGNORECASE), "refurbished"),
    (re.compile(r"\bd'?occasion\b", re.IGNORECASE), "used"),
    (re.compile(r"\bneuf\b", re.IGNORECASE), "new"),
    # Japanese
    (re.compile(r"整備済み|再生品|リファービッシュ", re.IGNORECASE), "refurbished"),
    (re.compile(r"中古", re.IGNORECASE), "used"),
    (re.compile(r"新品|未使用", re.IGNORECASE), "new"),
    # Korean
    (re.compile(r"리퍼|리퍼비시|재생", re.IGNORECASE), "refurbished"),
    (re.compile(r"중고", re.IGNORECASE), "used"),
    (re.compile(r"새상품|미개봉|새\s*제품", re.IGNORECASE), "new"),
    # Chinese
    (re.compile(r"翻新|翻新機|翻新机", re.IGNORECASE), "refurbished"),
    (re.compile(r"二手", re.IGNORECASE), "used"),
    (re.compile(r"全新|新品", re.IGNORECASE), "new"),
    # Arabic
    (re.compile(r"مجدد", re.IGNORECASE), "refurbished"),
    (re.compile(r"مستعمل", re.IGNORECASE), "used"),
    (re.compile(r"جديد", re.IGNORECASE), "new"),
]


# ============================================================
# Main Extraction Functions
# ============================================================


def extract_model(title: str) -> str | None:
    """Extract iPhone model from title.

    Args:
        title: Product title string.

    Returns:
        Normalized model string (e.g., "iphone-16-pro") or None.
    """
    for pattern, model in _MODEL_PATTERNS:
        if pattern.search(title):
            return model
    return None


def extract_storage(title: str) -> str | None:
    """Extract storage capacity from title.

    Args:
        title: Product title string.

    Returns:
        Normalized storage string (e.g., "256gb") or None.
    """
    matches = _STORAGE_PATTERN.findall(title)
    for amount, unit in matches:
        storage = f"{amount}{unit.lower()}"
        # Validate it's a real iPhone storage option
        if storage in _VALID_STORAGES:
            return storage
    return None


def extract_color(title: str) -> str | None:
    """Extract color from title.

    Args:
        title: Product title string.

    Returns:
        Normalized color string (e.g., "black") or None.
    """
    for pattern, color in _COLOR_PATTERNS:
        if pattern.search(title):
            return color
    return None


def extract_condition(title: str) -> str:
    """Extract condition from title.

    Args:
        title: Product title string.

    Returns:
        Normalized condition string. Defaults to "new" if not found.
    """
    for pattern, condition in _CONDITION_PATTERNS:
        if pattern.search(title):
            return condition
    # Default to "new" if no condition specified
    return "new"


def extract_attributes(title: str) -> ExtractionResult:
    """Extract all SKU attributes from a product title.

    Args:
        title: Product title string.

    Returns:
        ExtractionResult with attributes and confidence level.
    """
    model = extract_model(title)
    storage = extract_storage(title)
    color = extract_color(title)
    condition = extract_condition(title)

    # Build attributes dict
    attrs: SkuAttributes = {}
    if model:
        attrs["model"] = model
    if storage:
        attrs["storage"] = normalize_storage(storage)
    if color:
        attrs["color"] = normalize_color(color)
    attrs["condition"] = condition

    # Determine confidence
    confidence = _compute_confidence(model, storage, color)

    return ExtractionResult(
        attributes=attrs,
        confidence=confidence,
        raw_title=title,
        matched_model=model,
        matched_storage=storage,
        matched_color=color,
        matched_condition=condition,
    )


def _compute_confidence(
    model: str | None,
    storage: str | None,
    color: str | None,
) -> ExtractionConfidence:
    """Compute confidence level based on extracted attributes.

    Args:
        model: Extracted model or None.
        storage: Extracted storage or None.
        color: Extracted color or None.

    Returns:
        Confidence level.
    """
    # Model is required for any meaningful match
    if not model:
        return ExtractionConfidence.LOW

    # Count how many optional fields we got
    optional_count = sum([
        storage is not None,
        color is not None,
    ])

    if optional_count == 2:
        return ExtractionConfidence.HIGH
    elif optional_count == 1:
        return ExtractionConfidence.MEDIUM
    else:
        return ExtractionConfidence.LOW


def is_iphone_product(title: str) -> bool:
    """Quick check if a title likely refers to an iPhone product.

    Args:
        title: Product title string.

    Returns:
        True if title contains iPhone reference.
    """
    # Include a few common non-Latin spellings seen in local marketplaces.
    return bool(re.search(r"(?:\biphone\b|アイフォン|アイフォーン|아이폰)", title, re.IGNORECASE))


def filter_non_iphone_products(title: str) -> bool:
    """Check if title contains keywords indicating non-iPhone product.

    Args:
        title: Product title string.

    Returns:
        True if this is likely NOT an iPhone (case, screen protector, etc.).
    """
    exclusion_patterns = [
        # English
        r"\bcase\b",
        r"\bcover\b",
        r"\bprotector\b",
        r"\bscreen\b",
        r"\bcharger\b",
        r"\bcable\b",
        r"\badapter\b",
        r"\bstand\b",
        r"\bholder\b",
        r"\btempered\s*glass\b",
        r"\bfilm\b",
        r"\bskin\b",
        r"\bwallet\b",
        r"\bpouch\b",
        r"\bbattery\s*pack\b",
        r"\bpower\s*bank\b",
        r"\bearbuds\b",
        r"\bairpods\b",
        r"\bheadphones\b",
        r"\bwatch\b",
        r"\bipad\b",
        r"\bmac\b",
        # German
        r"\bh(ü|ue)lle\b",  # Hülle
        r"\bschutzfolie\b",
        r"\bdisplay(?:schutz|schutzfolie)?\b",
        r"\blade(?:gerät|kabel)\b",
        r"\bkopfhörer\b",
        # French
        r"\bcoque\b",
        r"\bétui\b",
        r"\bverre\s+trempé\b",
        r"\bfilm\s+de\s+protection\b",
        r"\bchargeur\b",
        r"\bcâble\b",
        r"\badaptateur\b",
        r"\bécouteurs\b",
        r"\bcasque\b",
        # Japanese (very common accessories)
        r"ケース",
        r"カバー",
        r"保護",
        r"保護フィルム",
        r"フィルム",
        r"ガラス",
        r"強化ガラス",
        r"充電器",
        r"ケーブル",
        r"アダプター",
        # Korean
        r"케이스",
        r"커버",
        r"보호필름",
        r"강화유리",
        r"충전기",
        r"케이블",
        r"어댑터",
        r"이어폰",
        r"헤드폰",
        r"거치대",
        # Chinese (HK/SG)
        r"保護殼|保护壳|手機殼|手机壳",
        r"保護套|保护套",
        r"保護膜|保护膜|貼膜|贴膜",
        r"玻璃貼|玻璃贴",
        r"充電器|充电器",
        r"數據線|数据线",
        r"轉接器|转接器",
        r"耳機|耳机",
        # Arabic (AE)
        r"جراب",
        r"غطاء",
        r"واقي\s*شاشة|واقي",
        r"شاحن",
        r"كابل",
        r"محول",
        r"سماعات",
    ]

    for pattern in exclusion_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False
