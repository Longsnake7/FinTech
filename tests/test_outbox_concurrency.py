"""Outbox repository concurrency helper tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.enums import OutboxEventType, OutboxStatus
from app.models import OutboxMessage
from app.repositories import OutboxRepository


@pytest.mark.asyncio
async def test_list_pending_uses_skip_locked() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    repo = OutboxRepository(session)
    await repo.list_pending(limit=10, now=datetime.now(UTC))

    session.execute.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "FOR UPDATE" in compiled.upper() or "for update" in compiled.lower()


@pytest.mark.asyncio
async def test_mark_processing_increments_attempts() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    repo = OutboxRepository(session)
    message = OutboxMessage(
        id=uuid4(),
        event_type=OutboxEventType.PAYMENTS_NEW.value,
        aggregate_type="payment",
        aggregate_id=uuid4(),
        payload={},
        status=OutboxStatus.PENDING,
        attempts=0,
        available_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    updated = await repo.mark_processing(message, lock_token="token")
    assert updated.status == OutboxStatus.PROCESSING
    assert updated.attempts == 1
    assert updated.lock_token == "token"
