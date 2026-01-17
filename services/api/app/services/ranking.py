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

import json

from sqlalchemy import select

from app.models import Offer, GoldenSku
from app.schemas import Deal, GuideStep
from app.stores.postgres import get_session


# Country code to flag emoji mapping
COUNTRY_FLAGS = {
    "JP": "🇯🇵",
    "US": "🇺🇸",
    "HK": "🇭🇰",
    "AE": "🇦🇪",
    "DE": "🇩🇪",
    "GB": "🇬🇧",
    "FR": "🇫🇷",
    "CN": "🇨🇳",
    "KR": "🇰🇷",
    "SG": "🇸🇬",
    "CA": "🇨🇦",
}


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
    async with get_session() as session:
        # Find the SKU
        sku_result = await session.execute(
            select(GoldenSku).where(GoldenSku.sku_key == sku_key)
        )
        sku = sku_result.scalar_one_or_none()

        if not sku:
            # Fallback: try to find any SKU matching the model
            model_key = "-".join(sku_key.split("-")[:3]) if "-" in sku_key else sku_key
            sku_result = await session.execute(
                select(GoldenSku).where(GoldenSku.model == model_key).limit(1)
            )
            sku = sku_result.scalar_one_or_none()

        if not sku:
            return []

        # Query offers for this SKU, filtered by trust score
        query = (
            select(Offer)
            .where(Offer.sku_id == sku.id)
            .where(Offer.trust_score >= min_trust)
            .order_by(Offer.final_effective_price.asc(), Offer.trust_score.desc())
            .limit(min(limit, 10))
        )

        result = await session.execute(query)
        offers = result.scalars().all()

        # Convert to Deal schemas
        deals: list[Deal] = []
        for rank, offer in enumerate(offers, start=1):
            # Parse guide steps from JSON
            guide_steps = []
            if offer.guide_steps_json:
                try:
                    steps_data = json.loads(offer.guide_steps_json)
                    guide_steps = [GuideStep(**step) for step in steps_data]
                except (json.JSONDecodeError, TypeError):
                    pass

            deal = Deal(
                offer_id=offer.offer_id,
                rank=rank,
                country_code=offer.country_code,
                country=offer.country,
                city=offer.city or "",
                flag=COUNTRY_FLAGS.get(offer.country_code, "🌍"),
                shop=offer.shop_name,
                availability=offer.availability,
                price_usd=offer.price_usd,
                tax_refund_value=offer.tax_refund_value,
                final_effective_price=offer.final_effective_price,
                local_price=offer.local_price_formatted,
                trust_score=offer.trust_score,
                sim_type=offer.sim_type or "",
                warranty=offer.warranty or "",
                restriction_alert=offer.restriction_alert,
                guide_steps=guide_steps,
            )
            deals.append(deal)

        return deals


async def get_total_offer_count(sku_key: str) -> int:
    """Get total number of offers for a SKU (before filtering).

    Args:
        sku_key: Golden SKU key.

    Returns:
        Total offer count.
    """
    async with get_session() as session:
        # Find the SKU
        sku_result = await session.execute(
            select(GoldenSku).where(GoldenSku.sku_key == sku_key)
        )
        sku = sku_result.scalar_one_or_none()

        if not sku:
            return 0

        # Count offers
        from sqlalchemy import func

        count_result = await session.execute(
            select(func.count(Offer.id)).where(Offer.sku_id == sku.id)
        )
        return count_result.scalar() or 0


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
