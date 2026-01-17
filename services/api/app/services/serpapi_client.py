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
from app.services.debug_storage import save_shopping_response, save_immersive_response

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
    second_hand_condition: str | None = None  # "refurbished", "used", "renewed", etc. (None = new)


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

        # Debug: save to file if enabled (instead of logging huge JSON)
        settings = get_settings()
        if settings.serpapi_debug:
            filename = save_shopping_response(query=query, gl=gl, data=data)
            if filename:
                logger.info(f"SerpAPI shopping response saved to debug file: {filename}")
            else:
                # Fallback to logging if file save failed
                logger.info(
                    f"SerpAPI shopping response (query={query}, gl={gl}):\n"
                    f"{json.dumps(data, indent=2, ensure_ascii=False)}"
                )

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

        # Debug: save to file if enabled (instead of logging huge JSON)
        settings = get_settings()
        if settings.serpapi_debug:
            filename = save_immersive_response(product_id=product_id, data=data)
            if filename:
                logger.info(f"SerpAPI immersive response saved to debug file: {filename}")
            else:
                # Fallback to logging if file save failed
                logger.info(
                    f"SerpAPI immersive response (product_id={product_id}):\n"
                    f"{json.dumps(data, indent=2, ensure_ascii=False)}"
                )

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
        """Parse google_shopping API response.

        Processes both:
        - shopping_results: Organic shopping listings (full product details, product_id, immersive tokens)
        - inline_shopping_results: Shopping ads (simpler structure, link instead of product_link, may lack product_id)
        """
        results: list[ShoppingResult] = []

        # Parse regular shopping_results
        shopping_results = data.get("shopping_results", [])
        for item in shopping_results:
            try:
                result = self._parse_shopping_item(item, gl, is_inline=False)
                if result and result.product_id and result.price > 0:
                    results.append(result)
            except Exception:
                continue

        # Parse inline_shopping_results (ads)
        inline_shopping_results = data.get("inline_shopping_results", [])
        for item in inline_shopping_results:
            try:
                result = self._parse_shopping_item(item, gl, is_inline=True)
                if result and result.price > 0:
                    # For inline results, product_id may be missing - use link hash as fallback
                    if not result.product_id:
                        # Generate stable ID from link
                        link = result.product_link
                        if link:
                            import hashlib
                            result.product_id = hashlib.sha256(link.encode()).hexdigest()[:16]
                        else:
                            continue  # Skip if no link and no product_id
                    results.append(result)
            except Exception:
                continue

        return results

    def _parse_shopping_item(self, item: dict[str, Any], gl: str, is_inline: bool = False) -> ShoppingResult | None:
        """Parse a single shopping result item (from shopping_results or inline_shopping_results).

        Args:
            item: Shopping result item dictionary.
            gl: Country code for currency inference.
            is_inline: True if from inline_shopping_results (ads), False if from shopping_results.

        Returns:
            ShoppingResult or None if parsing fails.
        """
        # Extract currency from multiple sources
        currency = self._extract_currency(item, gl)

        # Handle differences between shopping_results and inline_shopping_results:
        # - inline_shopping_results use "link" instead of "product_link"
        # - inline_shopping_results may not have "product_id"
        # - inline_shopping_results use "serpapi_immersive_product_api" (if present) differently
        product_link = item.get("product_link") or item.get("link", "")
        product_id = item.get("product_id", "")

        # For inline_shopping_results, immersive token might be in different format
        immersive_token = item.get("serpapi_product_api") or item.get("serpapi_immersive_product_api", "")

        return ShoppingResult(
            product_id=product_id,
            title=item.get("title", ""),
            price=self._parse_price(item.get("extracted_price", 0)),
            currency=currency,
            merchant=item.get("source", ""),
            product_link=product_link,
            immersive_token=immersive_token if immersive_token else None,
            thumbnail=item.get("thumbnail"),
            second_hand_condition=item.get("second_hand_condition"),  # None = new, "refurbished"/"used" = not new
        )

    def _extract_currency(self, item: dict[str, Any], gl: str = "us") -> str:
        """Extract currency from SerpAPI shopping result.

        Tries multiple sources:
        1. item.currency (direct field) - normalize if it's a symbol
        2. Parse from price string (¥, $, €, etc.)
        3. Infer from gl parameter (gl=jp → JPY, gl=de → EUR, etc.)
        4. alternative_price.currency - LAST RESORT only

        Rationale:
        - We store `price` from `extracted_price` (which corresponds to `item.price`),
          so currency must match the primary `item.price` field.
        - SerpAPI sometimes provides `alternative_price` in a different currency; using
          its currency alongside the primary extracted price would corrupt amounts.

        Args:
            item: Shopping result item from SerpAPI.
            gl: Google country code (e.g., "jp", "us", "de").

        Returns:
            Currency code (e.g., "JPY", "USD", "EUR").
        """
        # 1. Direct currency field (may be symbol or code)
        currency = item.get("currency")
        if currency:
            currency_str = str(currency).strip()
            # Normalize: if it's a symbol, convert to code
            normalized = self._normalize_currency_symbol(currency_str)
            if normalized:
                return normalized
            # If already a code (3+ chars), return uppercase
            if len(currency_str) >= 3:
                return currency_str.upper()

        # 2. Parse from price string
        price_str = item.get("price", "")
        if isinstance(price_str, str):
            currency_from_symbol = self._currency_from_symbol(price_str)
            if currency_from_symbol:
                return currency_from_symbol

        # 3. Infer from gl parameter
        inferred = self._currency_from_gl(gl)
        if inferred:
            return inferred

        # 4. Alternative price currency (last resort)
        alt_price = item.get("alternative_price", {})
        if isinstance(alt_price, dict):
            alt_currency = alt_price.get("currency")
            if alt_currency:
                alt_currency_str = str(alt_currency).strip()
                normalized = self._normalize_currency_symbol(alt_currency_str)
                if normalized:
                    return normalized
                if len(alt_currency_str) >= 3:
                    return alt_currency_str.upper()

        return "USD"

    def _normalize_currency_symbol(self, symbol: str) -> str | None:
        """Normalize currency symbol to ISO 4217 code.

        Handles cases where SerpAPI returns a symbol (₪, US$, £) instead of code.

        Args:
            symbol: Currency symbol or partial code.

        Returns:
            Currency code (e.g., "ILS", "USD", "GBP") or None if not recognized.
        """
        if not symbol:
            return None

        symbol = symbol.strip()

        # Direct mapping of common symbols to codes
        symbol_to_code = {
            "₪": "ILS",
            "US$": "USD",
            "$": "USD",
            "£": "GBP",
            "€": "EUR",
            "¥": "JPY",  # Default to JPY, but could be CNY based on gl
            "₩": "KRW",
            "HK$": "HKD",
            "S$": "SGD",
            "A$": "AUD",
            "C$": "CAD",
            "NZ$": "NZD",
            "₹": "INR",
            "R$": "BRL",
            "₽": "RUB",
            "₨": "PKR",
            "₦": "NGN",
            "₫": "VND",
            "₱": "PHP",
        }

        # Check exact match
        if symbol in symbol_to_code:
            return symbol_to_code[symbol]

        # If it's already a 3-letter code, return as-is (uppercase)
        if len(symbol) == 3 and symbol.isalpha():
            return symbol.upper()

        return None

    def _currency_from_symbol(self, price_str: str) -> str | None:
        """Extract currency code from price string with symbol.

        Examples:
            "¥159,800" → "JPY"
            "$1,099" → "USD"
            "US$1,099" → "USD"
            "€1,229" → "EUR"
            "£999" → "GBP"
            "₪14451.71" → "ILS"
        """
        if not price_str:
            return None

        # Currency symbol mapping (multi-character first, then single)
        # Note: ¥ is used for both JPY and CNY; we default to JPY here,
        # but gl parameter will override (gl=cn → CNY via _currency_from_gl)
        symbol_map = {
            "US$": "USD",
            "HK$": "HKD",
            "S$": "SGD",
            "A$": "AUD",
            "C$": "CAD",
            "NZ$": "NZD",
            "₪": "ILS",  # Israeli Shekel
            "¥": "JPY",  # Japanese Yen (also used for CNY, but gl=cn will override)
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "₩": "KRW",
            "₹": "INR",  # Indian Rupee
            "R$": "BRL",  # Brazilian Real
            "₽": "RUB",  # Russian Ruble
            "₨": "PKR",  # Pakistani Rupee
            "₦": "NGN",  # Nigerian Naira
            "₫": "VND",  # Vietnamese Dong
            "₱": "PHP",  # Philippine Peso
            "AED": "AED",
            "SAR": "SAR",  # Saudi Riyal
            "QAR": "QAR",  # Qatari Riyal
            "KWD": "KWD",  # Kuwaiti Dinar
            "BHD": "BHD",  # Bahraini Dinar
            "OMR": "OMR",  # Omani Rial
            "JOD": "JOD",  # Jordanian Dinar
        }

        # Check for multi-character symbols first (US$, HK$, S$, A$, etc.)
        for symbol, code in symbol_map.items():
            if len(symbol) > 1 and price_str.startswith(symbol):
                return code

        # Check single-character symbols
        first_char = price_str[0]
        return symbol_map.get(first_char)

    def _currency_from_gl(self, gl: str) -> str | None:
        """Infer currency from Google country code (gl parameter).

        Args:
            gl: Google country code (e.g., "jp", "us", "de").

        Returns:
            Default currency code for that country, or None if unknown.
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
            "ie": "EUR",
            "pt": "EUR",
            "gr": "EUR",
            "fi": "EUR",
            "dk": "DKK",
            "se": "SEK",
            "no": "NOK",
            "pl": "PLN",
            "cz": "CZK",
            "hu": "HUF",
            "ro": "RON",
            "bg": "BGN",
            "hr": "HRK",
            "hk": "HKD",
            "ae": "AED",
            "sg": "SGD",
            "kr": "KRW",
            "au": "AUD",
            "ca": "CAD",
            "nz": "NZD",
            "mx": "MXN",
            "br": "BRL",
            "in": "INR",
            "cn": "CNY",
            "il": "ILS",  # Israel
            "sa": "SAR",  # Saudi Arabia
            "qa": "QAR",  # Qatar
            "kw": "KWD",  # Kuwait
            "bh": "BHD",  # Bahrain
            "om": "OMR",  # Oman
            "jo": "JOD",  # Jordan
            "tr": "TRY",  # Turkey
            "ru": "RUB",  # Russia
            "za": "ZAR",  # South Africa
            "eg": "EGP",  # Egypt
            "th": "THB",  # Thailand
            "my": "MYR",  # Malaysia
            "id": "IDR",  # Indonesia
            "ph": "PHP",  # Philippines
            "vn": "VND",  # Vietnam
            "pk": "PKR",  # Pakistan
            "bd": "BDT",  # Bangladesh
            "ng": "NGN",  # Nigeria
        }
        return gl_to_currency.get(gl_lower)

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
