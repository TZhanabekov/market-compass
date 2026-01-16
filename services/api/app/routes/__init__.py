"""API routes."""

from fastapi import APIRouter

from app.routes import admin, redirect, ui

api_router = APIRouter()

# UI endpoints (Home bootstrap)
api_router.include_router(ui.router, prefix="/v1/ui", tags=["ui"])

# Redirect endpoint (CTA)
api_router.include_router(redirect.router, prefix="/r", tags=["redirect"])

# Admin endpoints (ingestion, management)
api_router.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
