"""Unit of Work wiring tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.uow import UnitOfWork
from app.repositories import OutboxRepository, PaymentRepository, ProcessedMessageRepository


@pytest.mark.asyncio
async def test_unit_of_work_binds_repositories_and_closes_session() -> None:
    session = AsyncMock()
    session.close = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    session_factory = MagicMock(return_value=session)

    async with UnitOfWork(session_factory) as uow:
        assert isinstance(uow.payments, PaymentRepository)
        assert isinstance(uow.outbox, OutboxRepository)
        assert isinstance(uow.processed_messages, ProcessedMessageRepository)
        await uow.commit()

    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()
    assert uow.session is None


@pytest.mark.asyncio
async def test_unit_of_work_rollbacks_on_error() -> None:
    session = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = MagicMock(return_value=session)

    with pytest.raises(RuntimeError, match="boom"):
        async with UnitOfWork(session_factory) as uow:
            assert uow.session is session
            raise RuntimeError("boom")

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
