"""SQLAlchemy ORM models.

Models represent database tables:
- golden_skus: Canonical product configurations
- merchants: Known merchants with trust tiers
- offers: Individual offers from merchants
- materialized_leaderboards: Pre-computed Top-10 for performance
"""

from app.models.offer import Offer
from app.models.sku import GoldenSku
from app.models.merchant import Merchant

__all__ = ["GoldenSku", "Merchant", "Offer"]
