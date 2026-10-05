"""Payment service unit tests."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import AnyHttpUrl

from app.domain.enums import Currency, PaymentStatus
from app.domain.exceptions import IdempotencyConflictError, PaymentNotFoundError
from app.models import Payment
from app.schemas.payments import PaymentCreateRequest
from app.services.payments import PaymentService


def _request() -> PaymentCreateRequest:
    return PaymentCreateRequest(
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="desc",
        metadata={"a": 1},
        webhook_url=AnyHttpUrl("https://example.com/hook"),
    )


@pytest.mark.asyncio
async def test_create_payment_writes_outbox() -> None:
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.outbox = AsyncMock()
    uow.session = AsyncMock()
    uow.payments.get_by_idempotency_key = AsyncMock(return_value=None)
    uow.payments.add = AsyncMock(side_effect=lambda p: p)
    uow.outbox.add = AsyncMock(side_effect=lambda m: m)
    uow.commit = AsyncMock()
    uow.session.refresh = AsyncMock(
        side_effect=lambda p: setattr(p, "created_at", datetime.now(UTC))
    )

    service = PaymentService(uow)
    payment = await service.create_payment(_request(), idempotency_key="k1")
    assert payment.status == PaymentStatus.PENDING
    uow.outbox.add.assert_awaited_once()
    uow.commit.assert_awaited_once()
    outbox = uow.outbox.add.await_args.args[0]
    assert outbox.payload["payment_id"] == str(payment.id)
    assert outbox.payload["event_id"] == str(outbox.id)


@pytest.mark.asyncio
async def test_create_payment_returns_existing_same_payload() -> None:
    existing = Payment(
        id=uuid4(),
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="desc",
        payment_metadata={"a": 1},
        status=PaymentStatus.PENDING,
        idempotency_key="k1",
        webhook_url="https://example.com/hook",
        created_at=datetime.now(UTC),
    )
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.outbox = AsyncMock()
    uow.session = AsyncMock()
    uow.payments.get_by_idempotency_key = AsyncMock(return_value=existing)

    service = PaymentService(uow)
    result = await service.create_payment(_request(), idempotency_key="k1")
    assert result.id == existing.id
    uow.payments.add.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_payment_conflict_different_payload() -> None:
    existing = Payment(
        id=uuid4(),
        amount=Decimal("99.00"),
        currency=Currency.USD,
        description="other",
        payment_metadata={},
        status=PaymentStatus.PENDING,
        idempotency_key="k1",
        webhook_url="https://example.com/hook",
        created_at=datetime.now(UTC),
    )
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.outbox = AsyncMock()
    uow.session = AsyncMock()
    uow.payments.get_by_idempotency_key = AsyncMock(return_value=existing)

    service = PaymentService(uow)
    with pytest.raises(IdempotencyConflictError):
        await service.create_payment(_request(), idempotency_key="k1")


@pytest.mark.asyncio
async def test_get_payment_not_found() -> None:
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.payments.get_by_id = AsyncMock(return_value=None)
    service = PaymentService(uow)
    with pytest.raises(PaymentNotFoundError):
        await service.get_payment(uuid4())
