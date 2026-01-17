"""Admin endpoints for ingestion and management.

These endpoints are intended for manual testing and admin operations.
In production, consider adding authentication (API key or admin token).
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models import GoldenSku
from app.services.reconciliation import reconcile_raw_offers
from app.services.dedup import compute_sku_key
from app.services.ingestion import (
    IngestionConfig,
    IngestionStats,
    ingest_offers_for_sku,
    COUNTRY_GL_MAP,
)
from app.services.attribute_extractor import ExtractionConfidence
from app.services.debug_storage import list_debug_files, get_debug_file
from app.services.fx import FxError, _fetch_openexchangerates_latest, _parse_openexchangerates_latest
from app.stores.postgres import get_session
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


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

class ReconcileRequest(BaseModel):
    """Request body for reconciliation endpoint."""

    limit: int = 500
    dry_run: bool = True
    country_code: str | None = None


class ReconcileResponse(BaseModel):
    """Response from reconciliation endpoint."""

    success: bool
    run_id: str
    dry_run: bool
    country_code: str | None
    stats: dict
    debug: dict


@router.post("/reconcile", response_model=ReconcileResponse)
async def trigger_reconcile(request: ReconcileRequest) -> ReconcileResponse:
    """Promote eligible raw_offers into offers.

    This is deterministic-only reconciliation. By default it runs in dry-run mode
    (rolls back changes) to avoid accidental writes in production.
    """
    run_id = str(uuid4())
    limit = max(1, min(int(request.limit), 5000))
    country_code = request.country_code.upper() if request.country_code else None

    logger.info(
        f"[reconcile] start run_id={run_id} limit={limit} dry_run={request.dry_run} country_code={country_code}"
    )

    try:
        async with get_session() as session:
            stats, debug = await reconcile_raw_offers(
                session=session,
                limit=limit,
                country_code=country_code,
            )

            # get_session() auto-commits on exit, so for dry runs we explicitly rollback
            # to ensure no writes are persisted.
            if request.dry_run:
                await session.rollback()
                logger.info(f"[reconcile] dry-run rollback run_id={run_id}")

        logger.info(
            "[reconcile] done run_id=%s scanned=%s created_offers=%s updated_raw=%s skipped_no_sku=%s skipped_fx=%s",
            run_id,
            stats.scanned,
            stats.created_offers,
            stats.updated_raw_matches,
            stats.skipped_no_sku,
            stats.skipped_fx,
        )

        return ReconcileResponse(
            success=True,
            run_id=run_id,
            dry_run=request.dry_run,
            country_code=country_code,
            stats={
                "scanned": stats.scanned,
                "skipped_multi_variant": stats.skipped_multi_variant,
                "skipped_contract": stats.skipped_contract,
                "skipped_missing_attrs": stats.skipped_missing_attrs,
                "skipped_no_sku": stats.skipped_no_sku,
                "skipped_fx": stats.skipped_fx,
                "dedup_conflict": stats.dedup_conflict,
                "matched_existing_offer": stats.matched_existing_offer,
                "created_offers": stats.created_offers,
                "updated_raw_matches": stats.updated_raw_matches,
            },
            debug={
                "created_offer_ids": debug.created_offer_ids,
                "matched_raw_offer_ids": debug.matched_raw_offer_ids,
                "sample_reason_codes": debug.sample_reason_codes,
            },
        )
    except Exception as e:
        logger.exception(f"[reconcile] failed run_id={run_id}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


# ============================================================
# Golden SKU Management
# ============================================================


class CreateSkuRequest(BaseModel):
    """Request body for creating a Golden SKU."""

    model: str  # e.g., "iphone-16-pro"
    storage: str  # e.g., "256gb"
    color: str  # e.g., "black"
    condition: str = "new"  # "new", "refurbished", "used"
    sim_variant: str | None = None
    lock_state: str | None = None
    region_variant: str | None = None
    display_name: str | None = None  # Auto-generated if not provided
    msrp_usd: float | None = None


class SkuResponse(BaseModel):
    """Response from SKU creation endpoint."""

    success: bool
    sku_key: str
    message: str


@router.post("/skus", response_model=SkuResponse)
async def create_golden_sku(request: CreateSkuRequest) -> SkuResponse:
    """Create a new Golden SKU.

    This endpoint creates a canonical SKU that can be used for ingestion.
    The sku_key is computed automatically from attributes.

    Args:
        request: SKU attributes.

    Returns:
        Created SKU key and status.
    """
    # Compute SKU key
    attrs = {
        "model": request.model,
        "storage": request.storage,
        "color": request.color,
        "condition": request.condition,
    }
    if request.sim_variant:
        attrs["sim_variant"] = request.sim_variant
    if request.lock_state:
        attrs["lock_state"] = request.lock_state
    if request.region_variant:
        attrs["region_variant"] = request.region_variant

    sku_key = compute_sku_key(attrs)

    # Generate display name if not provided
    display_name = request.display_name
    if not display_name:
        model_display = request.model.replace("-", " ").title()
        storage_display = request.storage.upper()
        color_display = request.color.title()
        display_name = f"{model_display} {storage_display} {color_display}"

    async with get_session() as session:
        # Check if exists
        result = await session.execute(
            select(GoldenSku).where(GoldenSku.sku_key == sku_key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            return SkuResponse(
                success=True,
                sku_key=sku_key,
                message=f"Golden SKU already exists: {sku_key}",
            )

        # Create new SKU
        sku = GoldenSku(
            sku_key=sku_key,
            model=request.model,
            storage=request.storage,
            color=request.color,
            condition=request.condition,
            sim_variant=request.sim_variant,
            lock_state=request.lock_state,
            region_variant=request.region_variant,
            display_name=display_name,
            msrp_usd=request.msrp_usd,
        )
        session.add(sku)
        await session.commit()

        return SkuResponse(
            success=True,
            sku_key=sku_key,
            message=f"Golden SKU created: {sku_key}",
        )


@router.get("/skus/{sku_key}")
async def get_golden_sku(sku_key: str) -> dict:
    """Get Golden SKU by key."""
    async with get_session() as session:
        result = await session.execute(
            select(GoldenSku).where(GoldenSku.sku_key == sku_key)
        )
        sku = result.scalar_one_or_none()

        if not sku:
            raise HTTPException(status_code=404, detail=f"Golden SKU not found: {sku_key}")

        return {
            "sku_key": sku.sku_key,
            "model": sku.model,
            "storage": sku.storage,
            "color": sku.color,
            "condition": sku.condition,
            "display_name": sku.display_name,
            "msrp_usd": sku.msrp_usd,
            "created_at": sku.created_at.isoformat() if sku.created_at else None,
        }


@router.get("/skus")
async def list_golden_skus(limit: int = Query(default=50, le=100)) -> dict:
    """List all Golden SKUs."""
    async with get_session() as session:
        result = await session.execute(
            select(GoldenSku).order_by(GoldenSku.created_at.desc()).limit(limit)
        )
        skus = result.scalars().all()

        return {
            "count": len(skus),
            "skus": [
                {
                    "sku_key": sku.sku_key,
                    "model": sku.model,
                    "storage": sku.storage,
                    "color": sku.color,
                    "display_name": sku.display_name,
                }
                for sku in skus
            ],
        }


# ============================================================
# Debug: SerpAPI Response Files
# ============================================================


@router.get("/debug/serpapi")
async def list_serpapi_debug_files(limit: int = Query(default=50, le=100)) -> dict:
    """List saved SerpAPI debug response files.

    Files are saved when SERPAPI_DEBUG=true is enabled.
    """
    files = list_debug_files(limit=limit)
    return {
        "count": len(files),
        "files": files,
    }


@router.get("/debug/serpapi/{filename}")
async def get_serpapi_debug_file(filename: str) -> JSONResponse:
    """Get SerpAPI debug response file content.

    Returns JSON response with full API data.
    """
    content = get_debug_file(filename)
    if not content:
        raise HTTPException(status_code=404, detail=f"Debug file not found: {filename}")

    return JSONResponse(content=content)


# ============================================================
# Debug: FX / OpenExchangeRates
# ============================================================


@router.get("/debug/fx")
async def debug_fx() -> dict:
    """Debug OpenExchangeRates response shape (sanitized).

    This helps diagnose issues like missing EUR rate in production without logging secrets.
    """
    try:
        raw = await _fetch_openexchangerates_latest()
        parsed = _parse_openexchangerates_latest(raw)

        rates_raw = raw.get("rates", {})
        keys = sorted([str(k).upper() for k in rates_raw.keys()]) if isinstance(rates_raw, dict) else []
        eur_raw = rates_raw.get("EUR") if isinstance(rates_raw, dict) else None
        eur_parsed = parsed.rates.get("EUR")

        # Surface common error fields when OXR returns error payloads
        error_payload = None
        if isinstance(raw, dict) and raw.get("error"):
            error_payload = {
                "error": raw.get("error"),
                "status": raw.get("status"),
                "message": raw.get("message"),
                "description": raw.get("description"),
            }

        return {
            "ok": True,
            "base": parsed.base,
            "timestamp": parsed.timestamp,
            "rates_count": len(parsed.rates),
            "eur_raw": eur_raw,
            "eur_parsed": eur_parsed,
            "sample_rate_keys": keys[:25],
            "error_payload": error_payload,
        }
    except FxError as e:
        return {"ok": False, "error": {"code": "FX_DEBUG_FAILED", "message": str(e), "detail": {}}}
