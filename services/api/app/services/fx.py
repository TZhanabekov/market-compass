"""FX (currency rates) service backed by OpenExchangeRates + Redis cache.

This module is used during ingestion to compute stable USD prices:
- Fetch latest rates from OpenExchangeRates (base USD on free tier)
- Cache rates in Redis for ~1 hour

If Redis is unavailable (e.g. tests / local minimal env), the service still works
but skips caching.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

import httpx

from app.settings import get_settings
from app.stores.redis import get_fx_rates_cache, set_fx_rates_cache

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class FxRates:
    base: str
    timestamp: int
    rates: dict[str, float]


class FxError(RuntimeError):
    pass


async def get_latest_fx_rates(base: str = "USD", *, force_refresh: bool = False) -> FxRates:
    """Get latest FX rates, using Redis cache when available.

    Args:
        base: Base currency. OpenExchangeRates free tier supports USD only.
        force_refresh: If True, bypass Redis cache and fetch from API once.
    """
    base = base.upper()
    if base != "USD":
        # OpenExchangeRates free tier supports base USD only.
        raise FxError("Only base=USD is supported")

    if not force_refresh:
        cached = await _try_get_cached_rates(base=base)
        if cached is not None:
            logger.info(f"FX rates loaded from cache: {len(cached.rates)} currencies")
            return cached

    logger.info("FX rates cache miss, fetching from OpenExchangeRates API...")
    fetched = await _fetch_openexchangerates_latest()
    rates = _parse_openexchangerates_latest(fetched)
    logger.info(f"FX rates fetched: {len(rates.rates)} currencies, EUR={rates.rates.get('EUR')}")

    await _try_set_cached_rates(base=base, rates=rates)
    return rates


async def convert_to_usd(
    amount: float,
    currency: str,
    *,
    rates: FxRates | None = None,
    retry_on_missing_rate: bool = True,
) -> float:
    """Convert an amount in `currency` to USD using OpenExchangeRates conventions.

    OpenExchangeRates returns rates as: 1 USD = rate[currency] units of currency.
    Therefore: USD = amount / rate[currency]
    """
    currency = currency.upper()
    if currency == "USD":
        return float(amount)

    if rates is None:
        logger.warning(f"No FX rates provided for {currency} conversion, fetching fresh rates")
    fx = rates or await get_latest_fx_rates(base="USD")
    rate = fx.rates.get(currency)
    if not rate or rate <= 0:
        if retry_on_missing_rate:
            # This can happen if Redis cache is corrupted/stale or OXR response was partial.
            # Retry once by bypassing cache to avoid dropping the offer unnecessarily.
            logger.warning(
                f"Currency {currency} missing in FX rates, forcing refresh from OpenExchangeRates and retrying once"
            )
            fresh = await get_latest_fx_rates(base="USD", force_refresh=True)
            return await convert_to_usd(
                amount,
                currency,
                rates=fresh,
                retry_on_missing_rate=False,
            )

        logger.error(
            f"Currency {currency} not found in FX rates. Available: {list(fx.rates.keys())[:10]}..."
        )
        raise FxError(f"Missing/invalid FX rate for {currency}")
    return float(amount) / float(rate)


async def _try_get_cached_rates(base: str) -> FxRates | None:
    try:
        payload = await get_fx_rates_cache(base=base)
    except RuntimeError:
        return None
    if not payload:
        return None

    try:
        ts = int(payload.get("timestamp", 0))
        rates_raw = payload.get("rates", {})
        if not isinstance(rates_raw, dict):
            return None
        rates: dict[str, float] = {
            str(k).upper(): float(v) for k, v in rates_raw.items() if v is not None
        }
        if not rates:
            return None
        return FxRates(base=base, timestamp=ts, rates=rates)
    except (TypeError, ValueError):
        return None


async def _try_set_cached_rates(base: str, rates: FxRates) -> None:
    payload: dict[str, Any] = {"base": rates.base, "timestamp": rates.timestamp, "rates": rates.rates}
    try:
        await set_fx_rates_cache(base=base, payload=payload)
    except RuntimeError:
        # Redis may be unavailable in tests/local minimal env.
        return


async def _fetch_openexchangerates_latest() -> dict[str, Any]:
    settings = get_settings()
    app_id = settings.openexchangerates_key
    if not app_id:
        logger.error("OPENEXCHANGERATES_KEY is not set - cannot fetch FX rates")
        raise FxError("OPENEXCHANGERATES_KEY is not set")

    url = "https://openexchangerates.org/api/latest.json"
    params = {"app_id": app_id}

    logger.info(f"Fetching FX rates from OpenExchangeRates (key={app_id[:8]}...)")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            logger.error(f"OpenExchangeRates API error: {resp.status_code} - {resp.text[:200]}")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise FxError("Unexpected response from OpenExchangeRates")
        return data


def _parse_openexchangerates_latest(data: dict[str, Any]) -> FxRates:
    base = str(data.get("base", "USD")).upper()
    # Free tier: base should be USD.
    if base != "USD":
        raise FxError(f"Unexpected base currency from OpenExchangeRates: {base}")

    timestamp = data.get("timestamp")
    if not isinstance(timestamp, int):
        # Fallback to "now" if timestamp is missing.
        timestamp = int(time.time())

    rates_raw = data.get("rates")
    if not isinstance(rates_raw, dict):
        raise FxError("Missing rates in OpenExchangeRates response")

    rates: dict[str, float] = {}
    for k, v in rates_raw.items():
        try:
            rates[str(k).upper()] = float(v)
        except (TypeError, ValueError):
            continue

    if not rates:
        raise FxError("Empty rates in OpenExchangeRates response")

    # Ensure USD is present
    rates.setdefault("USD", 1.0)

    return FxRates(base=base, timestamp=timestamp, rates=rates)

