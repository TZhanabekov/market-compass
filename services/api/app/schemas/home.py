"""Schemas for the Home UI endpoint (/v1/ui/home)."""

from datetime import datetime

from pydantic import BaseModel, Field


class GuideStep(BaseModel):
    """A single step in the deal guide."""

    icon: str
    title: str
    desc: str


class Deal(BaseModel):
    """A single deal in the leaderboard."""

    offer_id: str = Field(alias="offerId")
    rank: int = Field(ge=1, le=10)
    country_code: str = Field(alias="countryCode")
    country: str
    city: str
    flag: str
    shop: str
    availability: str
    price_usd: float = Field(alias="priceUsd")
    tax_refund_value: float = Field(alias="taxRefundValue", default=0)
    final_effective_price: float = Field(alias="finalEffectivePrice")
    local_price: str = Field(alias="localPrice")
    trust_score: int = Field(alias="trustScore", ge=0, le=100)
    sim_type: str = Field(alias="simType")
    warranty: str
    restriction_alert: str | None = Field(alias="restrictionAlert", default=None)
    guide_steps: list[GuideStep] = Field(alias="guideSteps", default_factory=list)

    model_config = {"populate_by_name": True}


class Leaderboard(BaseModel):
    """Leaderboard containing top deals."""

    deals: list[Deal] = Field(max_length=10)
    match_count: int = Field(alias="matchCount", ge=0)
    last_updated_at: datetime = Field(alias="lastUpdatedAt")

    model_config = {"populate_by_name": True}


class HomeMarket(BaseModel):
    """User's home market information."""

    country_code: str = Field(alias="countryCode")
    country: str
    currency: str
    local_price_usd: float = Field(alias="localPriceUsd")
    sim_type: str = Field(alias="simType")
    warranty: str

    model_config = {"populate_by_name": True}


class HomeResponse(BaseModel):
    """Response payload for GET /v1/ui/home.

    Matches the UI structure: homeMarket + leaderboard + winner.
    """

    model_key: str = Field(alias="modelKey")
    sku_key: str = Field(alias="skuKey")
    min_trust: int = Field(alias="minTrust", ge=0, le=100)
    home_market: HomeMarket = Field(alias="homeMarket")
    global_winner_offer_id: str = Field(alias="globalWinnerOfferId")
    leaderboard: Leaderboard

    model_config = {"populate_by_name": True}
