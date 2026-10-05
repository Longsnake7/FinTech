"""Test configuration and shared fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Return settings suitable for local unit tests."""
    return Settings(
        APP_NAME="payment-service-test",
        APP_ENV="test",
        DEBUG=False,
        API_KEY="test-api-key",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_USER="payment",
        POSTGRES_PASSWORD="payment",
        POSTGRES_DB="payments_test",
        DATABASE_URL="postgresql+asyncpg://payment:payment@localhost:5432/payments_test",
    )


@pytest.fixture
def app(settings: Settings):
    """Create a FastAPI app instance for tests."""
    return create_app(settings)


@pytest.fixture
def client(app) -> TestClient:
    """Synchronous test client."""
    with TestClient(app) as test_client:
        yield test_client
