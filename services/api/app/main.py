"""FastAPI application entry point.

Market Compass API - Global iPhone price intelligence.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import api_router
from app.settings import get_settings
from app.stores.postgres import init_db, close_db, ping_db
from app.stores.redis import init_redis, close_redis

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()

    # Initialize database (skip in tests if no DB available)
    try:
        await init_db()
        await ping_db()
        logger.info("Postgres connected")
    except Exception as e:
        logger.exception("Postgres init failed")

    # Initialize Redis (skip in tests if no Redis available)
    try:
        await init_redis()
    except Exception as e:
        logger.exception("Redis init failed")

    yield

    # Shutdown
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Global iPhone price intelligence API",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler for structured error format
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler returning structured error format."""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc) if settings.debug else "Internal server error",
                    "detail": None,
                }
            },
        )

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, bool]:
        """Health check endpoint."""
        return {"ok": True}

    # Include API routes
    app.include_router(api_router)

    return app


# Application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
