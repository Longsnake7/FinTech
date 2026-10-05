"""Repository interfaces and implementations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OutboxStatus
from app.models import OutboxMessage, Payment, ProcessedMessage


class PaymentRepository:
    """Data access for payments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> Payment:
        """Persist a new payment instance."""
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Fetch payment by primary key."""
        return await self._session.get(Payment, payment_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        """Fetch payment by idempotency key."""
        stmt: Select[tuple[Payment]] = select(Payment).where(
            Payment.idempotency_key == idempotency_key
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class OutboxRepository:
    """Data access for transactional outbox rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: OutboxMessage) -> OutboxMessage:
        """Persist a new outbox message."""
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_by_id(self, message_id: UUID) -> OutboxMessage | None:
        """Fetch outbox message by id."""
        return await self._session.get(OutboxMessage, message_id)

    async def list_pending(self, *, limit: int, now: datetime | None = None) -> list[OutboxMessage]:
        """Return pending outbox messages ready for publishing."""
        current = now or datetime.now(UTC)
        stmt = (
            select(OutboxMessage)
            .where(
                OutboxMessage.status == OutboxStatus.PENDING,
                OutboxMessage.available_at <= current,
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_processing(self, message: OutboxMessage, *, lock_token: str) -> OutboxMessage:
        """Mark outbox row as processing with a lock token."""
        message.status = OutboxStatus.PROCESSING
        message.locked_at = datetime.now(UTC)
        message.lock_token = lock_token
        message.attempts += 1
        await self._session.flush()
        return message

    async def mark_published(self, message: OutboxMessage) -> OutboxMessage:
        """Mark outbox row as successfully published."""
        message.status = OutboxStatus.PUBLISHED
        message.published_at = datetime.now(UTC)
        message.last_error = None
        message.lock_token = None
        message.locked_at = None
        await self._session.flush()
        return message

    async def mark_retry(
        self,
        message: OutboxMessage,
        *,
        error: str,
        available_at: datetime,
        failed: bool = False,
    ) -> OutboxMessage:
        """Schedule outbox row for retry or mark as permanently failed."""
        message.last_error = error
        message.lock_token = None
        message.locked_at = None
        if failed:
            message.status = OutboxStatus.FAILED
        else:
            message.status = OutboxStatus.PENDING
            message.available_at = available_at
        await self._session.flush()
        return message


class ProcessedMessageRepository:
    """Data access for consumer idempotency records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, message_id: str) -> bool:
        """Return True if message_id was already processed."""
        stmt = select(ProcessedMessage.id).where(ProcessedMessage.message_id == message_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, *, message_id: str, event_type: str) -> ProcessedMessage:
        """Mark a broker message as processed."""
        record = ProcessedMessage(message_id=message_id, event_type=event_type)
        self._session.add(record)
        await self._session.flush()
        return record

    async def try_acquire(self, *, message_id: str, event_type: str) -> bool:
        """
        Atomically claim a message for processing.

        Returns True if this caller acquired the claim, False if already processed.
        """
        from uuid import uuid4

        from sqlalchemy.dialects.postgresql import insert

        stmt = (
            insert(ProcessedMessage)
            .values(id=uuid4(), message_id=message_id, event_type=event_type)
            .on_conflict_do_nothing(index_elements=["message_id"])
            .returning(ProcessedMessage.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete(self, message_id: str) -> None:
        """Remove an idempotency record (used when releasing a failed claim)."""
        from sqlalchemy import delete

        await self._session.execute(
            delete(ProcessedMessage).where(ProcessedMessage.message_id == message_id)
        )
        await self._session.flush()
