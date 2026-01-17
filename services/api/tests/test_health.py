"""Tests for health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas import Deal


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health endpoint returns ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_home_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test home UI endpoint returns valid response."""
    # Avoid DB dependency: patch ranking calls used by the UI router.
    from app.routes import ui as ui_routes

    async def fake_get_top_deals(*, sku_key: str, min_trust: int = 80, limit: int = 10) -> list[Deal]:
        return [
            Deal(
                offer_id="offer-1",
                rank=1,
                country_code="DE",
                country="Germany",
                city="",
                flag="🇩🇪",
                shop="Test Shop",
                availability="In Stock",
                price_usd=999.0,
                tax_refund_value=0.0,
                final_effective_price=999.0,
                local_price="€999.00",
                trust_score=max(min_trust, 80),
                sim_type="",
                warranty="",
            )
        ][: min(limit, 10)]

    async def fake_get_total_offer_count(*, sku_key: str) -> int:
        return 1

    monkeypatch.setattr(ui_routes, "get_top_deals", fake_get_top_deals)
    monkeypatch.setattr(ui_routes, "get_total_offer_count", fake_get_total_offer_count)

    response = await client.get(
        "/v1/ui/home",
        params={"sku": "iphone-16-pro-256gb-black-new", "home": "DE", "minTrust": 80},
    )
    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "modelKey" in data
    assert "skuKey" in data
    assert "homeMarket" in data
    assert "leaderboard" in data
    assert "globalWinnerOfferId" in data

    # Check leaderboard structure
    assert "deals" in data["leaderboard"]
    assert "matchCount" in data["leaderboard"]
    assert len(data["leaderboard"]["deals"]) <= 10


@pytest.mark.asyncio
async def test_home_endpoint_trust_filter(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test that minTrust filter works."""
    from app.routes import ui as ui_routes

    async def fake_get_top_deals(*, sku_key: str, min_trust: int = 80, limit: int = 10) -> list[Deal]:
        # Simulate filtering: if minTrust too high, return no deals.
        if min_trust >= 99:
            return []
        return [
            Deal(
                offer_id="offer-1",
                rank=1,
                country_code="DE",
                country="Germany",
                city="",
                flag="🇩🇪",
                shop="Test Shop",
                availability="In Stock",
                price_usd=999.0,
                tax_refund_value=0.0,
                final_effective_price=999.0,
                local_price="€999.00",
                trust_score=80,
                sim_type="",
                warranty="",
            )
        ][: min(limit, 10)]

    async def fake_get_total_offer_count(*, sku_key: str) -> int:
        return 1

    monkeypatch.setattr(ui_routes, "get_top_deals", fake_get_top_deals)
    monkeypatch.setattr(ui_routes, "get_total_offer_count", fake_get_total_offer_count)

    # With high trust requirement
    response = await client.get(
        "/v1/ui/home",
        params={"sku": "iphone-16-pro-256gb-black-new", "home": "DE", "minTrust": 99},
    )
    assert response.status_code == 200
    data = response.json()

    # All returned deals should have trust >= 99
    for deal in data["leaderboard"]["deals"]:
        assert deal["trustScore"] >= 99
