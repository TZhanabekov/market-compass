"""SerpAPI client for Google Shopping and Immersive Product data.

Cost control rules:
- google_shopping is the primary feed (bulk ingestion)
- google_immersive_product is selective:
  - Eager: Top-1 (optionally Top-3)
  - Lazy: only on CTA click through /r/offers/{offerId}
- Never call immersive for every shopping result
- Always cache immersive results and use locks

Caching:
- Shopping responses: TTL 1-6 hours
- Immersive by token: TTL 7-30 days
- Merchant URL by offerId: TTL 7-30 days

Budget tracking:
- Record SerpAPI usage counters (calls/day)
"""

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from typing import Any

import httpx

from app.settings import get_settings
from app.stores.redis import (
    cache_get_json,
    cache_set_json,
    get_immersive_cache,
    set_immersive_cache,
    TTL_SHOPPING_CACHE,
    TTL_IMMERSIVE_CACHE,
)

logger = logging.getLogger("uvicorn.error")


@dataclass
class ShoppingResult:
    """Parsed result from google_shopping API."""

    product_id: str
    title: str
    price: float
    currency: str
    merchant: str
    product_link: str
    immersive_token: str | None = None
    thumbnail: str | None = None


@dataclass
class ImmersiveResult:
    """Parsed result from google_immersive_product API."""

    product_id: str
    merchant_url: str | None
    total_price: float | None = None
    shipping_cost: float | None = None


class SerpAPIClient:
    """Client for SerpAPI Google Shopping endpoints."""

    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str | None = None):
        """Initialize client with API key."""
        self.api_key = api_key or get_settings().serpapi_key
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def search_shopping(
        self,
        query: str,
        location: str | None = None,
        gl: str = "us",
        hl: str = "en",
        use_cache: bool = True,
    ) -> list[ShoppingResult]:
        """Search Google Shopping for products.

        This is the primary feed for bulk ingestion.
        Results are cached for 1-6 hours in Redis.

        Args:
            query: Search query (e.g., "iPhone 16 Pro 256GB").
            location: Optional location string.
            gl: Country code for Google (default: "us").
            hl: Language code (default: "en").
            use_cache: Whether to use Redis cache (default: True).

        Returns:
            List of shopping results.
        """
        if not self.api_key:
            logger.warning("SerpAPI key not configured, returning empty results")
            return []

        # Build cache key
        cache_key = self._build_shopping_cache_key(query, gl, hl, location)

        # Check cache first
        if use_cache:
            try:
                cached = await cache_get_json(cache_key)
                if cached:
                    logger.info(f"SerpAPI cache HIT for query={query}, gl={gl}")
                    return [ShoppingResult(**item) for item in cached]
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")

        # Make API call
        logger.info(f"SerpAPI cache MISS, calling API for query={query}, gl={gl}")

        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": gl,
            "hl": hl,
            "api_key": self.api_key,
        }

        if location:
            params["location"] = location

        client = await self._get_client()
        response = await client.get(self.BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()
        results = self._parse_shopping_results(data, gl=gl)

        # Cache results
        if use_cache and results:
            try:
                await cache_set_json(
                    cache_key,
                    [asdict(r) for r in results],
                    TTL_SHOPPING_CACHE,
                )
                logger.info(f"Cached {len(results)} shopping results for {cache_key}")
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")

        return results

    def _build_shopping_cache_key(
        self,
        query: str,
        gl: str,
        hl: str,
        location: str | None,
    ) -> str:
        """Build cache key for shopping results."""
        key_parts = f"{query}:{gl}:{hl}:{location or ''}"
        key_hash = hashlib.sha256(key_parts.encode()).hexdigest()[:16]
        return f"shopping:{key_hash}"

    async def get_immersive_product(
        self,
        product_id: str,
        use_cache: bool = True,
    ) -> ImmersiveResult | None:
        """Get detailed product info via google_immersive_product.

        This is the EXPENSIVE call - use selectively:
        - Eager: Top-1 (optionally Top-3)
        - Lazy: only on CTA click

        Results are cached for 7-30 days in Redis.

        Args:
            product_id: Product ID from shopping result.
            use_cache: Whether to use Redis cache (default: True).

        Returns:
            Immersive result with merchant URL, or None if failed.
        """
        if not self.api_key:
            logger.warning("SerpAPI key not configured for immersive call")
            return None

        # Check cache first
        if use_cache:
            try:
                cached = await get_immersive_cache(product_id)
                if cached:
                    logger.info(f"Immersive cache HIT for product_id={product_id}")
                    return ImmersiveResult(**cached)
            except Exception as e:
                logger.warning(f"Redis immersive cache read failed: {e}")

        # Make API call
        logger.info(f"Immersive cache MISS, calling API for product_id={product_id}")

        params = {
            "engine": "google_immersive_product",
            "product_id": product_id,
            "api_key": self.api_key,
        }

        client = await self._get_client()
        response = await client.get(self.BASE_URL, params=params)

        if response.status_code != 200:
            logger.warning(f"Immersive API returned {response.status_code} for {product_id}")
            return None

        data = response.json()
        result = self._parse_immersive_result(data, product_id)

        # Cache result
        if use_cache and result:
            try:
                await set_immersive_cache(product_id, asdict(result))
                logger.info(f"Cached immersive result for product_id={product_id}")
            except Exception as e:
                logger.warning(f"Redis immersive cache write failed: {e}")

        return result

    def _parse_shopping_results(self, data: dict[str, Any], gl: str = "us") -> list[ShoppingResult]:
        """Parse google_shopping API response."""
        results: list[ShoppingResult] = []

        shopping_results = data.get("shopping_results", [])
        for item in shopping_results:
            try:
                # Extract currency from multiple sources
                currency = self._extract_currency(item, gl)

                result = ShoppingResult(
                    product_id=item.get("product_id", ""),
                    title=item.get("title", ""),
                    price=self._parse_price(item.get("extracted_price", 0)),
                    currency=currency,
                    merchant=item.get("source", ""),
                    product_link=item.get("product_link", ""),
                    immersive_token=item.get("serpapi_product_api", ""),
                    thumbnail=item.get("thumbnail"),
                )
                if result.product_id and result.price > 0:
                    results.append(result)
            except Exception:
                continue

        return results

    def _extract_currency(self, item: dict[str, Any], gl: str = "us") -> str:
        """Extract currency from SerpAPI shopping result.

        Tries multiple sources:
        1. item.currency (direct field)
        2. alternative_price.currency
        3. Parse from price string (¥, $, €, etc.)
        4. Infer from gl parameter (gl=jp → JPY, gl=de → EUR, etc.)

        Args:
            item: Shopping result item from SerpAPI.
            gl: Google country code (e.g., "jp", "us", "de").

        Returns:
            Currency code (e.g., "JPY", "USD", "EUR").
        """
        # 1. Direct currency field
        currency = item.get("currency")
        if currency:
            return str(currency).upper()

        # 2. Alternative price currency
        alt_price = item.get("alternative_price", {})
        if isinstance(alt_price, dict):
            alt_currency = alt_price.get("currency")
            if alt_currency:
                return str(alt_currency).upper()

        # 3. Parse from price string
        price_str = item.get("price", "")
        if isinstance(price_str, str):
            currency_from_symbol = self._currency_from_symbol(price_str)
            if currency_from_symbol:
                return currency_from_symbol

        # 4. Infer from gl parameter
        return self._currency_from_gl(gl)

    def _currency_from_symbol(self, price_str: str) -> str | None:
        """Extract currency code from price string with symbol.

        Examples:
            "¥159,800" → "JPY"
            "$1,099" → "USD"
            "€1,229" → "EUR"
            "£999" → "GBP"
        """
        if not price_str:
            return None

        # Currency symbol mapping
        symbol_map = {
            "¥": "JPY",
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "HK$": "HKD",
            "S$": "SGD",
            "A$": "AUD",
            "₩": "KRW",
            "AED": "AED",
        }

        # Check for multi-character symbols first (HK$, S$, A$)
        for symbol, code in symbol_map.items():
            if len(symbol) > 1 and price_str.startswith(symbol):
                return code

        # Check single-character symbols
        first_char = price_str[0]
        return symbol_map.get(first_char)

    def _currency_from_gl(self, gl: str) -> str:
        """Infer currency from Google country code (gl parameter).

        Args:
            gl: Google country code (e.g., "jp", "us", "de").

        Returns:
            Default currency code for that country.
        """
        gl_lower = gl.lower()
        gl_to_currency = {
            "jp": "JPY",
            "us": "USD",
            "uk": "GBP",
            "gb": "GBP",
            "de": "EUR",
            "fr": "EUR",
            "it": "EUR",
            "es": "EUR",
            "nl": "EUR",
            "be": "EUR",
            "at": "EUR",
            "hk": "HKD",
            "ae": "AED",
            "sg": "SGD",
            "kr": "KRW",
            "au": "AUD",
            "ca": "CAD",
            "mx": "MXN",
            "br": "BRL",
            "in": "INR",
            "cn": "CNY",
        }
        return gl_to_currency.get(gl_lower, "USD")

    def _parse_immersive_result(
        self, data: dict[str, Any], product_id: str
    ) -> ImmersiveResult | None:
        """Parse google_immersive_product API response."""
        # Extract merchant URL from stores array
        stores = data.get("sellers_results", {}).get("online_sellers", [])
        merchant_url = None
        total_price = None

        for store in stores:
            link = store.get("link")
            if link and link.startswith("https://"):
                merchant_url = link
                total_price = self._parse_price(store.get("total_price", 0))
                break

        if not merchant_url:
            return None

        return ImmersiveResult(
            product_id=product_id,
            merchant_url=merchant_url,
            total_price=total_price,
        )

    def _parse_price(self, value: Any) -> float:
        """Parse price from various formats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = "".join(c for c in value if c.isdigit() or c == ".")
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


# Singleton client instance
_client: SerpAPIClient | None = None


def get_serpapi_client() -> SerpAPIClient:
    """Get SerpAPI client singleton."""
    global _client
    if _client is None:
        _client = SerpAPIClient()
    return _client
