"""Typed application config loaded from environment variables / .env file."""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_production(self) -> bool:
        """True when running in production environment."""
        return self.env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        """CORS allowed origins — locked down in production."""
        if self.is_production:
            return ["https://cryo.vercel.app"]
        return ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
