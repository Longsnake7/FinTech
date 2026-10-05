"""Payment use-cases."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.db.uow import UnitOfWork
from app.domain.enums import OutboxEventType, PaymentStatus
from app.domain.exceptions import IdempotencyConflictError, PaymentNotFoundError
from app.models import OutboxMessage, Payment
from app.schemas.payments import PaymentCreateRequest


class PaymentService:
    """Application service for payment commands/queries."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create_payment(
        self,
        payload: PaymentCreateRequest,
        *,
        idempotency_key: str,
    ) -> Payment:
        """
        Create a payment or return the existing one for the same idempotency key.

        Writes payment + outbox event in a single transaction.
        """
        assert self._uow.payments is not None
        assert self._uow.outbox is not None
        assert self._uow.session is not None

        existing = await self._uow.payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if self._payload_matches(existing, payload):
                return existing
            raise IdempotencyConflictError(idempotency_key)

        payment = Payment(
            id=uuid4(),
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            payment_metadata=payload.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            webhook_url=str(payload.webhook_url),
        )
        outbox_id = uuid4()

        try:
            await self._uow.payments.add(payment)
            await self._uow.session.refresh(payment)

            outbox = OutboxMessage(
                id=outbox_id,
                event_type=OutboxEventType.PAYMENTS_NEW.value,
                aggregate_type="payment",
                aggregate_id=payment.id,
                payload={
                    "event_id": str(outbox_id),
                    "event_type": OutboxEventType.PAYMENTS_NEW.value,
                    "payment_id": str(payment.id),
                    "attempt": 1,
                    "amount": str(payment.amount),
                    "currency": payment.currency.value
                    if hasattr(payment.currency, "value")
                    else str(payment.currency),
                    "description": payment.description,
                    "metadata": payment.payment_metadata,
                    "webhook_url": payment.webhook_url,
                    "idempotency_key": payment.idempotency_key,
                    "created_at": payment.created_at.isoformat(),
                },
            )
            await self._uow.outbox.add(outbox)
            await self._uow.commit()
        except IntegrityError as exc:
            await self._uow.rollback()
            raced = await self._uow.payments.get_by_idempotency_key(idempotency_key)
            if raced is not None and self._payload_matches(raced, payload):
                return raced
            if raced is not None:
                raise IdempotencyConflictError(idempotency_key) from exc
            raise

        return payment

    async def get_payment(self, payment_id: UUID) -> Payment:
        """Return payment by id or raise PaymentNotFoundError."""
        assert self._uow.payments is not None
        payment = await self._uow.payments.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))
        return payment

    @staticmethod
    def _payload_matches(payment: Payment, payload: PaymentCreateRequest) -> bool:
        amount = (
            payment.amount if isinstance(payment.amount, Decimal) else Decimal(str(payment.amount))
        )
        currency = (
            payment.currency.value if hasattr(payment.currency, "value") else str(payment.currency)
        )
        metadata: dict[str, Any] = payment.payment_metadata or {}
        return (
            amount == payload.amount
            and currency == payload.currency.value
            and payment.description == payload.description
            and metadata == payload.metadata
            and str(payment.webhook_url) == str(payload.webhook_url)
        )
