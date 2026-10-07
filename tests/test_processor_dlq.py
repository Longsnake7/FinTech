"""Processor DLQ helper tests."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.enums import Currency, PaymentStatus
from app.models import Payment
from app.services.processor import PaymentProcessor


@pytest.mark.asyncio
async def test_mark_payment_failed_updates_pending() -> None:
    payment_id = uuid4()
    payment = Payment(
        id=payment_id,
        amount=Decimal("1.00"),
        currency=Currency.USD,
        description="",
        payment_metadata={},
        status=PaymentStatus.PENDING,
        idempotency_key="k",
        webhook_url="https://example.com/hook",
        created_at=datetime.now(UTC),
    )
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.payments.get_by_id = AsyncMock(return_value=payment)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    processor = PaymentProcessor(
        uow_factory=lambda: uow,
        gateway=AsyncMock(),
        webhook_client=AsyncMock(),
    )
    await processor.mark_payment_failed(payment_id)
    assert payment.status == PaymentStatus.FAILED
    assert payment.processed_at is not None
    uow.commit.assert_awaited_once()
