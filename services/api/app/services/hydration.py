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

# Mock merchant URLs for initial implementation
# Will be replaced with actual DB/Redis/SerpAPI integration
_MOCK_MERCHANT_URLS = {
    "offer_jp_1": "https://www.biccamera.com/bc/item/10112345/",
    "offer_us_1": "https://www.apple.com/shop/buy-iphone/iphone-16-pro",
    "offer_hk_1": "https://www.fortress.com.hk/en/product/iphone-16-pro",
    "offer_ae_1": "https://www.sharafdg.com/product/iphone-16-pro",
}

# Fallback Google Shopping links
_MOCK_FALLBACK_URLS = {
    "offer_jp_1": "https://www.google.com/shopping/product/123?hl=en",
    "offer_us_1": "https://www.google.com/shopping/product/456?hl=en",
}


async def get_merchant_url(offer_id: str) -> str | None:
    """Get merchant URL for an offer, with lazy hydration.

    Priority:
    1. Redis cache (fast)
    2. PostgreSQL (persisted)
    3. SerpAPI hydration (expensive, cached after)

    Args:
        offer_id: The offer identifier.

    Returns:
        Merchant URL if found, None otherwise.
    """
    # TODO: Implement actual cache/DB/SerpAPI logic
    # For now, return mock data

    # Check mock merchant URLs
    if offer_id in _MOCK_MERCHANT_URLS:
        return _MOCK_MERCHANT_URLS[offer_id]

    # Check fallback URLs
    if offer_id in _MOCK_FALLBACK_URLS:
        return _MOCK_FALLBACK_URLS[offer_id]

    return None


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
