"""Payment processor idempotency and flow tests."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.enums import Currency, PaymentStatus
from app.domain.exceptions import PaymentGatewayError, UnknownEventMappingError
from app.models import Payment
from app.services.processor import PaymentProcessor


def _payment(**overrides) -> Payment:
    data = {
        "id": uuid4(),
        "amount": Decimal("10.00"),
        "currency": Currency.USD,
        "description": "x",
        "payment_metadata": {},
        "status": PaymentStatus.PENDING,
        "idempotency_key": "k",
        "webhook_url": "https://example.com/hook",
        "created_at": datetime.now(UTC),
        "processed_at": None,
    }
    data.update(overrides)
    return Payment(**data)


def _payload(payment: Payment, **overrides) -> dict:
    base = {
        "event_id": str(uuid4()),
        "event_type": "payments.new",
        "payment_id": str(payment.id),
        "attempt": 1,
        "amount": str(payment.amount),
        "currency": "USD",
        "description": payment.description,
        "metadata": {},
        "webhook_url": payment.webhook_url,
        "idempotency_key": payment.idempotency_key,
        "created_at": payment.created_at.isoformat(),
    }
    base.update(overrides)
    return base


def _uow_factory(uow: MagicMock):
    def factory():
        return uow

    return factory


@pytest.mark.asyncio
async def test_processor_success(settings) -> None:
    payment = _payment()
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.processed_messages = AsyncMock()
    uow.payments.get_by_id = AsyncMock(return_value=payment)
    uow.processed_messages.exists = AsyncMock(return_value=False)
    uow.processed_messages.try_acquire = AsyncMock(return_value=True)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    gateway = AsyncMock()
    gateway.process = AsyncMock()
    webhook = AsyncMock()
    webhook.notify = AsyncMock()

    processor = PaymentProcessor(
        uow_factory=_uow_factory(uow),
        gateway=gateway,
        webhook_client=webhook,
    )
    await processor.process(_payload(payment))
    gateway.process.assert_awaited_once()
    webhook.notify.assert_awaited_once()
    assert payment.status == PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_processor_skips_already_processed_message() -> None:
    payment = _payment()
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.processed_messages = AsyncMock()
    uow.processed_messages.exists = AsyncMock(return_value=True)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    gateway = AsyncMock()
    gateway.process = AsyncMock()
    webhook = AsyncMock()
    webhook.notify = AsyncMock()

    processor = PaymentProcessor(
        uow_factory=_uow_factory(uow),
        gateway=gateway,
        webhook_client=webhook,
    )
    await processor.process(_payload(payment))
    gateway.process.assert_not_awaited()
    webhook.notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_processor_duplicate_delivery_does_not_reprocess_succeeded() -> None:
    payment = _payment(status=PaymentStatus.SUCCEEDED, processed_at=datetime.now(UTC))
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.processed_messages = AsyncMock()
    uow.payments.get_by_id = AsyncMock(return_value=payment)
    uow.processed_messages.exists = AsyncMock(return_value=False)
    uow.processed_messages.try_acquire = AsyncMock(return_value=True)
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    gateway = AsyncMock()
    gateway.process = AsyncMock()
    webhook = AsyncMock()
    webhook.notify = AsyncMock()

    processor = PaymentProcessor(
        uow_factory=_uow_factory(uow),
        gateway=gateway,
        webhook_client=webhook,
    )
    await processor.process(_payload(payment))
    gateway.process.assert_not_awaited()
    webhook.notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_processor_gateway_error_propagates() -> None:
    payment = _payment()
    uow = MagicMock()
    uow.payments = AsyncMock()
    uow.processed_messages = AsyncMock()
    uow.payments.get_by_id = AsyncMock(return_value=payment)
    uow.processed_messages.exists = AsyncMock(return_value=False)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    gateway = AsyncMock()
    gateway.process = AsyncMock(side_effect=PaymentGatewayError("fail"))
    webhook = AsyncMock()
    webhook.notify = AsyncMock()

    processor = PaymentProcessor(
        uow_factory=_uow_factory(uow),
        gateway=gateway,
        webhook_client=webhook,
    )
    with pytest.raises(PaymentGatewayError):
        await processor.process(_payload(payment))
    webhook.notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_processor_unknown_mapping() -> None:
    processor = PaymentProcessor(
        uow_factory=lambda: MagicMock(),
        gateway=AsyncMock(),
        webhook_client=AsyncMock(),
    )
    with pytest.raises(UnknownEventMappingError):
        await processor.process({"event_type": "nope", "event_id": str(uuid4())})
