"""Tests for health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
async def test_home_endpoint(client: AsyncClient):
    """Test home UI endpoint returns valid response."""
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
async def test_home_endpoint_trust_filter(client: AsyncClient):
    """Test that minTrust filter works."""
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
