"""Settings tests."""

from app.config import Settings


def test_settings_builds_database_url_from_parts() -> None:
    settings = Settings(
        DATABASE_URL=None,
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="db",
        POSTGRES_PORT=5433,
        POSTGRES_DB="payments",
    )
    assert settings.sqlalchemy_database_uri == ("postgresql+asyncpg://u:p@db:5433/payments")


def test_settings_prefers_explicit_database_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://a:b@h:5432/db",
        POSTGRES_USER="ignored",
    )
    assert settings.sqlalchemy_database_uri == "postgresql+asyncpg://a:b@h:5432/db"
