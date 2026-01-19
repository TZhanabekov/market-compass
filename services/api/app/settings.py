"""Application settings via Pydantic Settings."""

from functools import lru_cache
import json
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _asyncpg_connect_args_from_url(database_url: str) -> dict[str, object]:
    """
    Compute asyncpg connect_args based on DATABASE_URL.

    Railway Postgres uses an internal hostname (e.g. postgres.railway.internal)
    that rejects SSL negotiation. In that case we must explicitly disable SSL.
    """
    host = urlparse(database_url).hostname or ""
    if host.endswith(".railway.internal"):
        # Internal Railway Postgres rejects SSL negotiation; also add a timeout
        # because the DB may not be ready at container start.
        return {"ssl": False, "timeout": 20}
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
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> list[str]:
        """
        Accept either:
        - JSON array string: '["https://a.com","http://localhost:3000"]'
        - Comma-separated string: "https://a.com,http://localhost:3000"
        - Already-parsed list[str]
        """
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                except json.JSONDecodeError:
                    # Fall back to comma split if env var isn't valid JSON.
                    parsed = s.split(",")
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
                return [str(parsed).strip()]
            return [part.strip() for part in s.split(",") if part.strip()]
        return [str(v).strip()] if str(v).strip() else []

    # SerpAPI
    serpapi_key: str = Field(
        default="",
        validation_alias=AliasChoices("SERPAPI_API_KEY", "SERPAPI_KEY"),
    )
    serpapi_debug: bool = Field(
        default=False,
        description="If True, log full SerpAPI response JSON for debugging",
    )

    # OpenExchangeRates (for future use)
    openexchangerates_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENEXCHANGERATES_KEY", "OPENEXCHANGERATES_APP_ID"),
    )

    # LLM (optional parsing/matching fallback)
    llm_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LLM_ENABLED"),
        description="Enable GPT-5-mini fallback parsing/matching (off by default).",
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY"),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL"),
    )
    openai_model_parse: str = Field(
        default="gpt-5-mini",
        validation_alias=AliasChoices("OPENAI_MODEL_PARSE"),
    )
    llm_max_calls_per_reconcile: int = Field(
        default=50,
        validation_alias=AliasChoices("LLM_MAX_CALLS_PER_RECONCILE"),
        ge=0,
        le=5000,
    )
    llm_max_fraction_per_reconcile: float = Field(
        default=0.2,
        validation_alias=AliasChoices("LLM_MAX_FRACTION_PER_RECONCILE"),
        ge=0.0,
        le=1.0,
    )

    # LLM pattern suggestions (admin)
    pattern_suggest_max_concurrency: int = Field(
        default=2,
        validation_alias=AliasChoices("PATTERN_SUGGEST_MAX_CONCURRENCY"),
        ge=1,
        le=8,
        description="Max concurrent OpenAI requests for /v1/admin/patterns/suggest",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
