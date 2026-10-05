"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the payment service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="payment-service", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    api_key: str = Field(default="change-me-api-key", alias="API_KEY")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="payment", alias="POSTGRES_USER")
    postgres_password: str = Field(default="payment", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="payments", alias="POSTGRES_DB")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    outbox_poll_interval_seconds: float = Field(default=1.0, alias="OUTBOX_POLL_INTERVAL_SECONDS")
    outbox_batch_size: int = Field(default=50, alias="OUTBOX_BATCH_SIZE")
    outbox_max_attempts: int = Field(default=5, alias="OUTBOX_MAX_ATTEMPTS")
    message_max_attempts: int = Field(default=3, alias="MESSAGE_MAX_ATTEMPTS")
    retry_base_delay_seconds: float = Field(default=1.0, alias="RETRY_BASE_DELAY_SECONDS")
    retry_max_delay_seconds: float = Field(default=30.0, alias="RETRY_MAX_DELAY_SECONDS")
    retry_jitter_seconds: float = Field(default=0.5, alias="RETRY_JITTER_SECONDS")
    gateway_success_rate: float = Field(default=0.9, alias="GATEWAY_SUCCESS_RATE")
    gateway_min_delay_seconds: float = Field(default=2.0, alias="GATEWAY_MIN_DELAY_SECONDS")
    gateway_max_delay_seconds: float = Field(default=5.0, alias="GATEWAY_MAX_DELAY_SECONDS")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return async SQLAlchemy DSN."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
