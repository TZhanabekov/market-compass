"""Trust score calculation service.

Trust Score (0-100) is a composite metric based on:
- Merchant reputation (verified, known retailer, etc.)
- Price anomaly detection (too good to be true)
- Data completeness (shipping, warranty info available)
- Source reliability (official store vs marketplace)
"""

from dataclasses import dataclass
from enum import Enum


class MerchantTier(Enum):
    """Merchant trust tier."""

    OFFICIAL = "official"  # Apple Store, carrier stores
    VERIFIED = "verified"  # Known retailers (Bic Camera, MediaMarkt, etc.)
    MARKETPLACE = "marketplace"  # Amazon, eBay marketplace sellers
    UNKNOWN = "unknown"  # Unverified merchants


@dataclass
class TrustFactors:
    """Factors contributing to trust score."""

    merchant_tier: MerchantTier
    has_shipping_info: bool = True
    has_warranty_info: bool = True
    has_return_policy: bool = True
    price_within_expected_range: bool = True
    verified_stock: bool = False
    has_physical_address: bool = False


# Base scores by merchant tier
_TIER_BASE_SCORES = {
    MerchantTier.OFFICIAL: 95,
    MerchantTier.VERIFIED: 85,
    MerchantTier.MARKETPLACE: 60,
    MerchantTier.UNKNOWN: 40,
}

# Score adjustments
_ADJUSTMENTS = {
    "missing_shipping": -10,
    "missing_warranty": -10,
    "missing_return_policy": -5,
    "price_anomaly": -20,
    "verified_stock": +5,
    "has_physical_address": +5,
}


def calculate_trust_score_with_reasons(factors: TrustFactors) -> tuple[int, list[str]]:
    """Calculate trust score and return compact reason codes.

    Reason codes are stable strings intended for persistence / explainability.
    """
    score = _TIER_BASE_SCORES[factors.merchant_tier]
    reasons: list[str] = [f"TIER_{factors.merchant_tier.name}"]

    if not factors.has_shipping_info:
        score += _ADJUSTMENTS["missing_shipping"]
        reasons.append("MISSING_SHIPPING")
    if not factors.has_warranty_info:
        score += _ADJUSTMENTS["missing_warranty"]
        reasons.append("MISSING_WARRANTY")
    if not factors.has_return_policy:
        score += _ADJUSTMENTS["missing_return_policy"]
        reasons.append("MISSING_RETURN_POLICY")
    if not factors.price_within_expected_range:
        score += _ADJUSTMENTS["price_anomaly"]
        reasons.append("PRICE_ANOMALY")
    if factors.verified_stock:
        score += _ADJUSTMENTS["verified_stock"]
        reasons.append("VERIFIED_STOCK")
    if factors.has_physical_address:
        score += _ADJUSTMENTS["has_physical_address"]
        reasons.append("HAS_PHYSICAL_ADDRESS")

    # Clamp to 0-100
    clamped = max(0, min(100, score))
    if clamped != score:
        reasons.append("CLAMPED")
    return clamped, reasons


def calculate_trust_score(factors: TrustFactors) -> int:
    """Calculate trust score from factors.

    Args:
        factors: Trust factors for the offer.

    Returns:
        Trust score (0-100).
    """
    score, _ = calculate_trust_score_with_reasons(factors)
    return score


def detect_price_anomaly(
    price_usd: float,
    expected_min: float,
    expected_max: float,
) -> bool:
    """Detect if a price is suspiciously low or high.

    Args:
        price_usd: Actual price in USD.
        expected_min: Minimum expected price (e.g., 70% of MSRP).
        expected_max: Maximum expected price (e.g., 130% of MSRP).

    Returns:
        True if price is anomalous (outside expected range).
    """
    return price_usd < expected_min or price_usd > expected_max


# Known merchant tier mappings
_KNOWN_MERCHANTS: dict[str, MerchantTier] = {
    "apple store": MerchantTier.OFFICIAL,
    "apple": MerchantTier.OFFICIAL,
    "bic camera": MerchantTier.VERIFIED,
    "yodobashi": MerchantTier.VERIFIED,
    "mediamarkt": MerchantTier.VERIFIED,
    "saturn": MerchantTier.VERIFIED,
    "best buy": MerchantTier.VERIFIED,
    "fortress hk": MerchantTier.VERIFIED,
    "sharaf dg": MerchantTier.VERIFIED,
    "amazon": MerchantTier.MARKETPLACE,
    "ebay": MerchantTier.MARKETPLACE,
}


def get_merchant_tier(merchant_name: str) -> MerchantTier:
    """Get trust tier for a merchant by name.

    Args:
        merchant_name: Merchant name (case-insensitive).

    Returns:
        MerchantTier for the merchant.
    """
    normalized = merchant_name.lower().strip()
    return _KNOWN_MERCHANTS.get(normalized, MerchantTier.UNKNOWN)
