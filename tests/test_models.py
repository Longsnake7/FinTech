"""ORM model smoke tests."""

from decimal import Decimal
from uuid import uuid4

from app.domain.enums import Currency, OutboxEventType, OutboxStatus, PaymentStatus
from app.models import OutboxMessage, Payment, ProcessedMessage


def test_payment_model_defaults() -> None:
    payment = Payment(
        id=uuid4(),
        amount=Decimal("1.00"),
        currency=Currency.USD,
        description="x",
        payment_metadata={},
        status=PaymentStatus.PENDING,
        idempotency_key="key-1",
        webhook_url="https://example.com/hook",
    )
    assert payment.status is PaymentStatus.PENDING
    assert payment.processed_at is None


def test_outbox_and_processed_message_models() -> None:
    aggregate_id = uuid4()
    outbox = OutboxMessage(
        id=uuid4(),
        event_type=OutboxEventType.PAYMENTS_NEW.value,
        aggregate_type="payment",
        aggregate_id=aggregate_id,
        payload={"payment_id": str(aggregate_id)},
        status=OutboxStatus.PENDING,
    )
    processed = ProcessedMessage(
        id=uuid4(),
        message_id=str(outbox.id),
        event_type=OutboxEventType.PAYMENTS_NEW.value,
    )
    assert outbox.status is OutboxStatus.PENDING
    assert processed.message_id == str(outbox.id)
