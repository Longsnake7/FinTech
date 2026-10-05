"""Payment event processing (consumer business logic)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.db.uow import UnitOfWork
from app.domain.enums import OutboxEventType, PaymentStatus
from app.domain.exceptions import PaymentNotFoundError, UnknownEventMappingError
from app.schemas.payments import PaymentCreatedEvent
from app.services.gateway import PaymentGateway
from app.services.webhook import WebhookClient


class PaymentProcessor:
    """Handles payments.new events with idempotent business effects."""

    def __init__(
        self,
        *,
        uow_factory: Any,
        gateway: PaymentGateway,
        webhook_client: WebhookClient,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway
        self._webhook_client = webhook_client
        self._handlers = {
            OutboxEventType.PAYMENTS_NEW.value: self._handle_payments_new,
        }

    async def process(self, payload: dict[str, Any]) -> None:
        """
        Route and process a broker payload.

        Raises UnknownEventMappingError when event_type has no handler.
        Re-raises processing errors for retry/DLQ handling by the consumer.
        """
        event_type = str(payload.get("event_type", ""))
        handler = self._handlers.get(event_type)
        if handler is None:
            raise UnknownEventMappingError(event_type or "<missing>")
        await handler(payload)

    async def _handle_payments_new(self, payload: dict[str, Any]) -> None:
        event = PaymentCreatedEvent.model_validate(payload)
        message_id = str(event.event_id)

        async with self._uow_factory() as uow:
            assert uow.processed_messages is not None
            assert uow.payments is not None

            if await uow.processed_messages.exists(message_id):
                return

            payment = await uow.payments.get_by_id(event.payment_id)
            if payment is None:
                raise PaymentNotFoundError(str(event.payment_id))

            already_final = payment.status != PaymentStatus.PENDING

        if not already_final:
            await self._gateway.process(payment)
            async with self._uow_factory() as uow:
                assert uow.payments is not None
                db_payment = await uow.payments.get_by_id(event.payment_id)
                if db_payment is None:
                    raise PaymentNotFoundError(str(event.payment_id))
                if db_payment.status == PaymentStatus.PENDING:
                    db_payment.status = PaymentStatus.SUCCEEDED
                    db_payment.processed_at = datetime.now(UTC)
                await uow.commit()
                payment = db_payment

        await self._webhook_client.notify(payment)

        async with self._uow_factory() as uow:
            assert uow.processed_messages is not None
            await uow.processed_messages.try_acquire(
                message_id=message_id,
                event_type=event.event_type,
            )
            await uow.commit()

    async def mark_payment_failed(self, payment_id: UUID) -> None:
        """Mark payment failed after retries are exhausted (DLQ path)."""
        async with self._uow_factory() as uow:
            assert uow.payments is not None
            payment = await uow.payments.get_by_id(payment_id)
            if payment is None:
                return
            if payment.status == PaymentStatus.PENDING:
                payment.status = PaymentStatus.FAILED
                payment.processed_at = datetime.now(UTC)
                await uow.commit()


def create_uow_factory(session_factory: Any) -> Any:
    """Build a zero-arg async context factory for UnitOfWork."""

    def factory() -> UnitOfWork:
        return UnitOfWork(session_factory)

    return factory
