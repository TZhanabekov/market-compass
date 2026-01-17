"""UI bootstrap endpoints.

GET /v1/ui/home - Returns HomeResponse for the main page.

Routers are thin: call services for business logic.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.schemas import HomeMarket, HomeResponse, Leaderboard
from app.services.ranking import get_top_deals, get_total_offer_count

router = APIRouter()


@router.get("/home", response_model=HomeResponse)
async def get_home(
    sku: str = Query(
        default="iphone-16-pro-256gb-black-new",
        description="Golden SKU key",
        examples=["iphone-16-pro-256gb-black-new"],
    ),
    home: str = Query(
        default="DE",
        description="Home country code (ISO 3166-1 alpha-2)",
        min_length=2,
        max_length=2,
        examples=["DE", "US", "GB"],
    ),
    min_trust: int = Query(
        default=80,
        alias="minTrust",
        ge=0,
        le=100,
        description="Minimum trust score filter (0-100)",
    ),
    lang: str = Query(
        default="en",
        description="Language for guides",
        min_length=2,
        max_length=5,
        examples=["en", "de", "ru"],
    ),
) -> HomeResponse:
    """Get home screen data with Top-10 deals.

    Returns:
        HomeResponse with homeMarket, leaderboard (<=10 deals), and winner ID.
    """
    # Extract model key from SKU (e.g., "iphone-16-pro-256gb-black-new" -> "iphone-16-pro")
    model_key = "-".join(sku.split("-")[:3]) if "-" in sku else sku

    # Get ranked deals from service (handles filtering by minTrust)
    deals = await get_top_deals(sku_key=sku, min_trust=min_trust, limit=10)

    # Get total offer count (before filtering)
    total_count = await get_total_offer_count(sku_key=sku)

    # Determine global winner (first deal after ranking)
    global_winner_id = deals[0].offer_id if deals else ""

    # Build home market info (will be fetched from DB in future)
    home_market = HomeMarket(
        country_code=home.upper(),
        country=_get_country_name(home.upper()),
        currency=_get_currency(home.upper()),
        local_price_usd=1299.0,  # Will come from DB
        sim_type="eSIM + nanoSIM",
        warranty="EU consumer warranty (varies by retailer)",
    )

    return HomeResponse(
        model_key=model_key,
        sku_key=sku,
        min_trust=min_trust,
        home_market=home_market,
        global_winner_offer_id=global_winner_id,
        leaderboard=Leaderboard(
            deals=deals,
            match_count=total_count,
            last_updated_at=datetime.now(timezone.utc),
        ),
    )


def _get_country_name(code: str) -> str:
    """Get country name from code. Will be replaced with DB lookup."""
    countries = {
        "DE": "Germany",
        "US": "United States",
        "GB": "United Kingdom",
        "JP": "Japan",
        "HK": "Hong Kong",
        "AE": "United Arab Emirates",
        "FR": "France",
        "CA": "Canada",
    }
    return countries.get(code, code)


def _get_currency(code: str) -> str:
    """Get currency from country code. Will be replaced with DB lookup."""
    currencies = {
        "DE": "EUR",
        "US": "USD",
        "GB": "GBP",
        "JP": "JPY",
        "HK": "HKD",
        "AE": "AED",
        "FR": "EUR",
        "CA": "CAD",
    }
    return currencies.get(code, "USD")
