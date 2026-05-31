"""Application configuration loaded from environment variables.

All settings can be overridden via a .env file or environment variables.
See .env.example for the full list of configurable values.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — SQLite for local dev, PostgreSQL for production
    database_url: str = "sqlite+aiosqlite:///./email_context.db"

    # JWT authentication
    jwt_secret_key: str = "change-me-to-a-random-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # Fernet key for at-rest encryption of email summaries
    encryption_key: str = "your-fernet-key-here"

    # Google Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # In-memory cache TTL (seconds). Set to 0 to disable caching.
    cache_ttl_seconds: int = 1800

    # Partial-refresh: minimum new emails required to trigger re-summarisation
    summarization_min_new_emails: int = 5
    summarization_max_retries: int = 3
    summarization_retry_base_delay: float = 1.0

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
