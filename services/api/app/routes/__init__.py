"""API routes."""

from fastapi import APIRouter

from app.routes import redirect, ui

api_router = APIRouter()

# UI endpoints (Home bootstrap)
api_router.include_router(ui.router, prefix="/v1/ui", tags=["ui"])

# Redirect endpoint (CTA)
api_router.include_router(redirect.router, prefix="/r", tags=["redirect"])
