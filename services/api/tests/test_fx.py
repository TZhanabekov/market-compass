import pytest

from app.services.fx import FxError, FxRates, _parse_openexchangerates_latest, convert_to_usd


def test_parse_openexchangerates_latest_ok():
    fx = _parse_openexchangerates_latest(
        {"base": "USD", "timestamp": 1700000000, "rates": {"EUR": 0.8, "JPY": 150}}
    )
    assert fx.base == "USD"
    assert fx.timestamp == 1700000000
    assert fx.rates["EUR"] == 0.8
    assert fx.rates["JPY"] == 150.0
    assert fx.rates["USD"] == 1.0


def test_parse_openexchangerates_latest_rejects_non_usd_base():
    with pytest.raises(FxError):
        _parse_openexchangerates_latest({"base": "EUR", "timestamp": 1, "rates": {"USD": 1.2}})


@pytest.mark.asyncio
async def test_convert_to_usd_uses_provided_rates():
    rates = FxRates(base="USD", timestamp=1, rates={"EUR": 0.8, "USD": 1.0})
    usd = await convert_to_usd(80.0, "EUR", rates=rates)
    assert usd == 100.0


@pytest.mark.asyncio
async def test_convert_to_usd_missing_rate_raises():
    rates = FxRates(base="USD", timestamp=1, rates={"USD": 1.0})
    with pytest.raises(FxError):
        await convert_to_usd(10.0, "GBP", rates=rates)

