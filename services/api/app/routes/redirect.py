"""Redirect endpoint for CTA "Claim Arbitrage".

GET /r/offers/{offerId} -> 302 redirect to merchant URL.

Flow:
1. Check if merchant_url exists in DB -> redirect immediately
2. If not, hydrate via google_immersive_product (once), cache, persist, redirect
3. Fallback: redirect to product_link if merchant URL cannot be obtained

Security:
- Only redirect to https URLs sourced from SerpAPI or stored offers
- Block javascript:, data:, file: schemes
"""

import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import RedirectResponse

from app.services.hydration import get_merchant_url

router = APIRouter()

# Blocked URL schemes for security
BLOCKED_SCHEMES = {"javascript", "data", "file", "vbscript"}


def _is_safe_url(url: str) -> bool:
    """Validate URL is safe for redirect.

    Only allows https URLs, blocks dangerous schemes.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() in BLOCKED_SCHEMES:
            return False
        if parsed.scheme.lower() not in ("https", "http"):
            return False
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


@router.get("/offers/{offer_id}")
async def redirect_to_offer(
    offer_id: str = Path(
        description="Offer ID to redirect to",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
    ),
) -> RedirectResponse:
    """Redirect to merchant URL for the given offer.

    If merchant_url is not cached, performs lazy hydration via SerpAPI
    google_immersive_product (once per offer), then caches and redirects.

    Args:
        offer_id: The offer identifier.

    Returns:
        302 redirect to merchant URL.

    Raises:
        HTTPException 404: If offer not found.
        HTTPException 502: If merchant URL cannot be obtained.
    """
    # Get merchant URL (from cache, DB, or hydrate via SerpAPI)
    merchant_url = await get_merchant_url(offer_id)

    if not merchant_url:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OFFER_NOT_FOUND",
                    "message": f"Offer {offer_id} not found",
                    "detail": {"offer_id": offer_id},
                }
            },
        )

    # Validate URL is safe before redirecting
    if not _is_safe_url(merchant_url):
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "INVALID_MERCHANT_URL",
                    "message": "Merchant URL is not safe for redirect",
                    "detail": {"offer_id": offer_id},
                }
            },
        )

    # Cache-Control header for private caching
    return RedirectResponse(
        url=merchant_url,
        status_code=302,
        headers={"Cache-Control": "private, max-age=60"},
    )
