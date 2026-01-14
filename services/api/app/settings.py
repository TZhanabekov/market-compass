"""Application settings via Pydantic Settings."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def _asyncpg_connect_args_from_url(database_url: str) -> dict[str, object]:
    """
    Compute asyncpg connect_args based on DATABASE_URL.

    Railway Postgres uses an internal hostname (e.g. postgres.railway.internal)
    that rejects SSL negotiation. In that case we must explicitly disable SSL.
    """
    host = urlparse(database_url).hostname or ""
    if host.endswith(".railway.internal"):
        return {"ssl": False}
    return {}


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Market Compass API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Database (PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/market_compass"

    @property
    def async_database_url(self) -> str:
        """Get database URL with asyncpg driver.

        Railway provides postgresql:// but we need postgresql+asyncpg:// for async.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def asyncpg_connect_args(self) -> dict[str, object]:
        """Extra connect args for asyncpg (e.g. Railway SSL quirks)."""
        return _asyncpg_connect_args_from_url(self.async_database_url)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # SerpAPI (for future use)
    serpapi_key: str = ""

    # OpenExchangeRates (for future use)
    openexchangerates_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
