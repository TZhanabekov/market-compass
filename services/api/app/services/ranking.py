"""Ranking service for Top-10 deal selection.

Ranking logic:
1. Sort by effective_price_usd ASC (cheapest first)
2. Then by trust_score DESC (higher trust breaks ties)
3. Then by availability (in stock preferred)

Risk slider:
- Filter by trust_score >= minTrust
- Return <= 10 deals
- Include matchCount (total before filtering)
"""

from app.schemas import Deal, GuideStep

# Mock data for initial implementation
# Will be replaced with DB queries
_MOCK_DEALS = [
    Deal(
        offer_id="offer_jp_1",
        rank=1,
        country_code="JP",
        country="Japan",
        city="Tokyo",
        flag="🇯🇵",
        shop="Bic Camera",
        availability="In Stock",
        price_usd=741,
        tax_refund_value=65,
        final_effective_price=676,
        local_price="¥112,800",
        trust_score=98,
        sim_type="eSIM + Physical SIM",
        warranty="1-Year Apple Global",
        restriction_alert="Camera shutter sound always on (J/A model)",
        guide_steps=[
            GuideStep(
                icon="map-pin",
                title="Where to Buy",
                desc="Bic Camera Yurakucho. Show passport at checkout for tax-free price.",
            ),
            GuideStep(
                icon="plane",
                title="Airport Refund",
                desc="Narita Terminal 2, 'Customs' counter before security. Goods must be sealed.",
            ),
            GuideStep(
                icon="cpu",
                title="Hardware Check",
                desc="Verify Model A3102. Shutter sound is permanent.",
            ),
        ],
    ),
    Deal(
        offer_id="offer_us_1",
        rank=2,
        country_code="US",
        country="United States",
        city="Delaware",
        flag="🇺🇸",
        shop="Apple Store",
        availability="Limited",
        price_usd=799,
        tax_refund_value=0,
        final_effective_price=799,
        local_price="$799",
        trust_score=100,
        sim_type="eSIM Only (No Physical Slot)",
        warranty="1-Year Apple Global",
        restriction_alert="Model LL/A - No physical SIM tray.",
        guide_steps=[
            GuideStep(
                icon="map-pin",
                title="Tax-Free State",
                desc="Buy in Delaware or Oregon for 0% sales tax at register.",
            ),
            GuideStep(
                icon="cpu",
                title="Important Info",
                desc="Ensure your home carrier supports eSIM before buying.",
            ),
        ],
    ),
    Deal(
        offer_id="offer_hk_1",
        rank=3,
        country_code="HK",
        country="Hong Kong",
        city="Central",
        flag="🇭🇰",
        shop="Fortress HK",
        availability="In Stock",
        price_usd=815,
        tax_refund_value=0,
        final_effective_price=815,
        local_price="HK$6,350",
        trust_score=94,
        sim_type="Dual Physical SIM",
        warranty="1-Year Apple Global",
        restriction_alert="Dual Physical SIM slots supported (ZA/A model)",
        guide_steps=[
            GuideStep(
                icon="map-pin",
                title="Where to Buy",
                desc="Fortress HK in Central or Apple Causeway Bay for official pricing.",
            ),
            GuideStep(
                icon="check",
                title="Free Port",
                desc="HK is a free port. No VAT refund needed, prices are already net.",
            ),
        ],
    ),
    Deal(
        offer_id="offer_ae_1",
        rank=4,
        country_code="AE",
        country="UAE",
        city="Dubai",
        flag="🇦🇪",
        shop="Sharaf DG",
        availability="In Stock",
        price_usd=845,
        tax_refund_value=35,
        final_effective_price=810,
        local_price="AED 3,100",
        trust_score=92,
        sim_type="eSIM + Physical SIM",
        warranty="1-Year Apple Global",
        restriction_alert="FaceTime usually works outside UAE, but verify.",
        guide_steps=[
            GuideStep(
                icon="plane",
                title="Planet Tax Free",
                desc="Scan QR code at Planet kiosks in DXB Terminal 3 before checking bags.",
            ),
            GuideStep(
                icon="alert-triangle",
                title="FaceTime Note",
                desc="FaceTime is disabled in UAE but usually activates when abroad.",
            ),
        ],
    ),
]


async def get_top_deals(
    sku_key: str,
    min_trust: int = 80,
    limit: int = 10,
) -> list[Deal]:
    """Get top deals for a given SKU, filtered by trust score.

    Args:
        sku_key: Golden SKU key to filter by.
        min_trust: Minimum trust score (0-100).
        limit: Maximum number of deals to return (default 10, max 10).

    Returns:
        List of Deal objects, sorted by effective_price_usd ASC, trust_score DESC.
    """
    # Filter by trust score
    filtered = [d for d in _MOCK_DEALS if d.trust_score >= min_trust]

    # Sort: effective_price ASC, trust_score DESC
    sorted_deals = sorted(
        filtered,
        key=lambda d: (d.final_effective_price, -d.trust_score),
    )

    # Limit to max 10
    result = sorted_deals[: min(limit, 10)]

    # Re-assign ranks after filtering
    for i, deal in enumerate(result, start=1):
        deal.rank = i

    return result


async def calculate_effective_price(
    base_price_usd: float,
    tax_refund_value: float = 0,
    shipping_cost: float = 0,
    import_duty: float = 0,
) -> float:
    """Calculate effective price including all costs/savings.

    Formula: base_price - tax_refund + shipping + import_duty

    Args:
        base_price_usd: Base price in USD.
        tax_refund_value: Tax refund amount (subtracted).
        shipping_cost: Shipping cost (added).
        import_duty: Import duty/customs (added).

    Returns:
        Effective price in USD.
    """
    return base_price_usd - tax_refund_value + shipping_cost + import_duty
