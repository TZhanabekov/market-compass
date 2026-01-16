"""Admin endpoints for ingestion and management.

These endpoints are intended for manual testing and admin operations.
In production, consider adding authentication (API key or admin token).
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.ingestion import (
    IngestionConfig,
    IngestionStats,
    ingest_offers_for_sku,
    COUNTRY_GL_MAP,
)
from app.services.attribute_extractor import ExtractionConfidence

router = APIRouter()


class IngestionRequest(BaseModel):
    """Request body for ingestion endpoint."""

    sku_key: str
    country_code: str
    min_confidence: str = "medium"  # "high", "medium", "low"
    skip_low_confidence: bool = True
    update_existing: bool = True


class IngestionResponse(BaseModel):
    """Response from ingestion endpoint."""

    success: bool
    stats: dict


@router.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(request: IngestionRequest) -> IngestionResponse:
    """Trigger ingestion for a specific SKU and country.

    This endpoint calls SerpAPI, processes results, and persists offers to DB.

    Args:
        request: Ingestion parameters.

    Returns:
        Ingestion statistics.
    """
    # Validate country code
    if request.country_code.upper() not in COUNTRY_GL_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported country code: {request.country_code}. "
                   f"Supported: {list(COUNTRY_GL_MAP.keys())}",
        )

    # Map confidence string to enum
    confidence_map = {
        "high": ExtractionConfidence.HIGH,
        "medium": ExtractionConfidence.MEDIUM,
        "low": ExtractionConfidence.LOW,
    }
    min_conf = confidence_map.get(request.min_confidence.lower(), ExtractionConfidence.MEDIUM)

    config = IngestionConfig(
        min_confidence=min_conf,
        skip_low_confidence=request.skip_low_confidence,
        update_existing=request.update_existing,
    )

    try:
        stats = await ingest_offers_for_sku(
            sku_key=request.sku_key,
            country_code=request.country_code,
            config=config,
        )

        return IngestionResponse(
            success=True,
            stats={
                "query": stats.query,
                "country_code": stats.country_code,
                "total_results": stats.total_results,
                "filtered_accessories": stats.filtered_accessories,
                "low_confidence": stats.low_confidence,
                "no_sku_match": stats.no_sku_match,
                "duplicates": stats.duplicates,
                "new_offers": stats.new_offers,
                "updated_offers": stats.updated_offers,
                "errors": stats.errors,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.get("/ingest/countries")
async def get_supported_countries() -> dict:
    """Get list of supported countries for ingestion."""
    return {
        "countries": list(COUNTRY_GL_MAP.keys()),
        "default": "US",
    }
