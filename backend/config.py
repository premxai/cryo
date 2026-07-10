"""Typed application config loaded from environment variables / .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config in one place — never use os.environ[] directly in app code."""

    # External APIs (required in later milestones, optional here so M1 boots without them)
    anthropic_api_key: str = ""
    gptzero_api_key: str = ""

    # Search infrastructure
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_key: str = "cryo_dev_key"
    qdrant_url: str = "http://localhost:6333"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:cryo@localhost:5432/cryo"
    redis_url: str = "redis://localhost:6379"

    # App
    env: str = "development"
    log_level: str = "INFO"

    # Embedding (used from M3)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_ttl_seconds: int = 86400

    # Claude judge model (used from M4)
    judge_model: str = "claude-3-5-haiku-20241022"

    # SaaS API (v1) — free tier limits
    free_tier_monthly_quota: int = 1000
    free_tier_rate_per_minute: int = 60

    # /v1/contents — Wayback live fetch
    wayback_timeout_seconds: int = 25
    contents_max_items: int = 10
    contents_negative_cache_ttl: int = 3600

    # /v1/list-domain — the CDX index is erratically slow on cold wildcard queries
    cdx_timeout_seconds: int = 75

    # Self-serve signup (Phase 4)
    resend_api_key: str = ""
    public_base_url: str = "http://localhost:5173"
    session_secret: str = "dev_session_secret_change_me"
    session_ttl_hours: int = 72
    magic_link_ttl_minutes: int = 15

    # CORS — comma-separated origin list; falls back to env defaults when empty
    allowed_origins_env: str = Field(default="", validation_alias="ALLOWED_ORIGINS")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }

    @property
    def is_production(self) -> bool:
        """True when running in production environment."""
        return self.env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        """CORS allowed origins — from ALLOWED_ORIGINS env var, locked down in production."""
        if self.allowed_origins_env:
            return [o.strip() for o in self.allowed_origins_env.split(",") if o.strip()]
        if self.is_production:
            return ["https://cryo.vercel.app"]
        return ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
