"""Deduplication service for Golden SKU matching and offer dedup.

Golden SKU:
- Compute stable sku_key from normalized attributes:
  model + storage + color + condition (+ optional sim_variant/lock_state/region_variant)

Offer dedup within leaderboard:
- Dedup key: merchant + price + currency (+ url hash if available)
"""

import hashlib
import re
from typing import TypedDict


class SkuAttributes(TypedDict, total=False):
    """Normalized SKU attributes."""

    model: str  # e.g., "iphone-16-pro"
    storage: str  # e.g., "256gb"
    color: str  # e.g., "black"
    condition: str  # e.g., "new", "refurbished"
    sim_variant: str | None  # e.g., "esim-only", "dual-sim"
    lock_state: str | None  # e.g., "unlocked", "carrier-locked"
    region_variant: str | None  # e.g., "us", "eu", "jp"


def compute_sku_key(attrs: SkuAttributes) -> str:
    """Compute stable SKU key from normalized attributes.

    Format: {model}-{storage}-{color}-{condition}[-{sim_variant}][-{lock_state}][-{region}]

    Args:
        attrs: Normalized SKU attributes.

    Returns:
        Stable SKU key string.

    Example:
        >>> compute_sku_key({"model": "iphone-16-pro", "storage": "256gb", "color": "black", "condition": "new"})
        "iphone-16-pro-256gb-black-new"
    """
    parts = [
        _normalize(attrs.get("model", "")),
        _normalize(attrs.get("storage", "")),
        _normalize(attrs.get("color", "")),
        _normalize(attrs.get("condition", "new")),
    ]

    # Add optional components if present
    if attrs.get("sim_variant"):
        parts.append(_normalize(attrs["sim_variant"]))
    if attrs.get("lock_state"):
        parts.append(_normalize(attrs["lock_state"]))
    if attrs.get("region_variant"):
        parts.append(_normalize(attrs["region_variant"]))

    return "-".join(p for p in parts if p)


def compute_offer_dedup_key(
    merchant: str,
    price: float,
    currency: str,
    url: str | None = None,
) -> str:
    """Compute deduplication key for an offer.

    Format: {merchant_normalized}:{price}:{currency}[:url_hash]

    Args:
        merchant: Merchant name.
        price: Price value.
        currency: Currency code.
        url: Optional URL for additional uniqueness.

    Returns:
        Dedup key string.
    """
    parts = [
        _normalize(merchant),
        f"{price:.2f}",
        currency.upper(),
    ]

    if url:
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
        parts.append(url_hash)

    return ":".join(parts)


def _normalize(value: str) -> str:
    """Normalize a string for key generation.

    - Lowercase
    - Replace spaces/underscores with hyphens
    - Remove special characters
    - Collapse multiple hyphens
    """
    if not value:
        return ""

    result = value.lower().strip()
    result = re.sub(r"[\s_]+", "-", result)
    result = re.sub(r"[^a-z0-9-]", "", result)
    result = re.sub(r"-+", "-", result)
    return result.strip("-")


def normalize_storage(raw: str) -> str:
    """Normalize storage values (e.g., '256 GB' -> '256gb').

    Args:
        raw: Raw storage string.

    Returns:
        Normalized storage string.
    """
    # Remove spaces, lowercase
    normalized = raw.lower().replace(" ", "")
    # Ensure consistent format
    match = re.match(r"(\d+)\s*(gb|tb)", normalized)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return normalized


def normalize_color(raw: str) -> str:
    """Normalize color values.

    Maps common variations to standard names.

    Args:
        raw: Raw color string.

    Returns:
        Normalized color string.
    """
    color_map = {
        "space black": "black",
        "space gray": "gray",
        "space grey": "gray",
        "natural titanium": "natural",
        "white titanium": "white",
        "black titanium": "black",
        "desert titanium": "desert",
        "blue titanium": "blue",
    }

    normalized = raw.lower().strip()
    return color_map.get(normalized, _normalize(normalized))
