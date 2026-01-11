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

from dataclasses import dataclass
from typing import Any

import httpx

from app.settings import get_settings


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
    ) -> list[ShoppingResult]:
        """Search Google Shopping for products.

        This is the primary feed for bulk ingestion.
        Results should be cached for 1-6 hours.

        Args:
            query: Search query (e.g., "iPhone 16 Pro 256GB").
            location: Optional location string.
            gl: Country code for Google (default: "us").
            hl: Language code (default: "en").

        Returns:
            List of shopping results.
        """
        if not self.api_key:
            return []

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
        return self._parse_shopping_results(data)

    async def get_immersive_product(
        self,
        product_id: str,
    ) -> ImmersiveResult | None:
        """Get detailed product info via google_immersive_product.

        This is the EXPENSIVE call - use selectively:
        - Eager: Top-1 (optionally Top-3)
        - Lazy: only on CTA click

        Results should be cached for 7-30 days.

        Args:
            product_id: Product ID from shopping result.

        Returns:
            Immersive result with merchant URL, or None if failed.
        """
        if not self.api_key:
            return None

        params = {
            "engine": "google_immersive_product",
            "product_id": product_id,
            "api_key": self.api_key,
        }

        client = await self._get_client()
        response = await client.get(self.BASE_URL, params=params)

        if response.status_code != 200:
            return None

        data = response.json()
        return self._parse_immersive_result(data, product_id)

    def _parse_shopping_results(self, data: dict[str, Any]) -> list[ShoppingResult]:
        """Parse google_shopping API response."""
        results: list[ShoppingResult] = []

        shopping_results = data.get("shopping_results", [])
        for item in shopping_results:
            try:
                result = ShoppingResult(
                    product_id=item.get("product_id", ""),
                    title=item.get("title", ""),
                    price=self._parse_price(item.get("extracted_price", 0)),
                    currency=item.get("currency", "USD"),
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
