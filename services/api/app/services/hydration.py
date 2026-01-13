"""Lazy hydration service for merchant URLs.

Flow:
1. Check Redis cache for merchant_url
2. Check PostgreSQL for persisted merchant_url
3. If not found, call SerpAPI google_immersive_product (once)
4. Cache result in Redis (long TTL) and persist to DB
5. Use locks to prevent thundering herd

Cost control:
- Only hydrate on CTA click (lazy)
- Cache immersive results for 7-30 days
- Lock per offerId to prevent duplicate calls
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Offer
from app.settings import get_settings

# Database connection
_engine = None
_session_factory = None


async def _get_session() -> AsyncSession:
    """Get database session."""
    global _engine, _session_factory

    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.async_database_url, echo=settings.debug)
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )

    return _session_factory()


async def get_merchant_url(offer_id: str) -> str | None:
    """Get merchant URL for an offer, with lazy hydration.

    Priority:
    1. Redis cache (fast) - TODO: implement
    2. PostgreSQL (persisted)
    3. SerpAPI hydration (expensive, cached after) - TODO: implement

    Args:
        offer_id: The offer identifier.

    Returns:
        Merchant URL if found, None otherwise.
    """
    session = await _get_session()

    try:
        # Query offer from database
        result = await session.execute(
            select(Offer).where(Offer.offer_id == offer_id)
        )
        offer = result.scalar_one_or_none()

        if not offer:
            return None

        # If merchant_url exists, return it
        if offer.merchant_url:
            return offer.merchant_url

        # Fallback to product_link (Google Shopping link)
        return offer.product_link

    finally:
        await session.close()


async def hydrate_merchant_url(offer_id: str, immersive_token: str) -> str | None:
    """Hydrate merchant URL via SerpAPI google_immersive_product.

    This is the expensive operation - should only be called once per offer,
    with results cached for 7-30 days.

    Args:
        offer_id: The offer identifier.
        immersive_token: Token from google_shopping result.

    Returns:
        Merchant URL if successfully hydrated, None otherwise.
    """
    # TODO: Implement actual SerpAPI call
    # 1. Acquire lock for offer_id (prevent thundering herd)
    # 2. Double-check cache (in case another request hydrated)
    # 3. Call SerpAPI google_immersive_product
    # 4. Extract stores[].link
    # 5. Persist to DB
    # 6. Cache in Redis (long TTL)
    # 7. Release lock

    return None
