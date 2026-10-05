"""Test configuration and shared fixtures."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.enums import Currency, PaymentStatus
from app.main import create_app
from app.models import Payment


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
        OUTBOX_WORKER_ENABLED=False,
        MESSAGE_MAX_ATTEMPTS=3,
        RETRY_BASE_DELAY_SECONDS=1.0,
        RETRY_MAX_DELAY_SECONDS=30.0,
        RETRY_JITTER_SECONDS=0.5,
        GATEWAY_SUCCESS_RATE=0.9,
        GATEWAY_MIN_DELAY_SECONDS=2.0,
        GATEWAY_MAX_DELAY_SECONDS=5.0,
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


@pytest.fixture
def api_headers(settings: Settings) -> dict[str, str]:
    """Default authenticated headers."""
    return {
        "X-API-Key": settings.api_key,
        "Idempotency-Key": "idem-test-key-1",
    }


@pytest.fixture
def sample_payment() -> Payment:
    """Build a sample payment entity."""
    return Payment(
        id=uuid4(),
        amount=Decimal("100.00"),
        currency=Currency.USD,
        description="Test",
        payment_metadata={"order_id": "1"},
        status=PaymentStatus.PENDING,
        idempotency_key="idem-test-key-1",
        webhook_url="https://example.com/webhook",
        created_at=datetime.now(UTC),
        processed_at=None,
    )


@pytest.fixture
def mock_publisher() -> AsyncMock:
    """Async mock for MessagePublisher protocol."""
    publisher = AsyncMock()
    publisher.publish_payments_new = AsyncMock()
    publisher.publish_retry = AsyncMock()
    publisher.publish_dlq = AsyncMock()
    return publisher


@pytest.fixture
def mock_uow() -> MagicMock:
    """Unit of Work mock with repository mocks."""
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.outbox = AsyncMock()
    uow.processed_messages = AsyncMock()
    uow.session = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow
