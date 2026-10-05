"""Async Unit of Work for transactional boundaries."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories import OutboxRepository, PaymentRepository, ProcessedMessageRepository


class UnitOfWork:
    """Coordinates repositories within a single database transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.payments: PaymentRepository | None = None
        self.outbox: OutboxRepository | None = None
        self.processed_messages: ProcessedMessageRepository | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.payments = PaymentRepository(self.session)
        self.outbox = OutboxRepository(self.session)
        self.processed_messages = ProcessedMessageRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self.session.close()
            self.session = None
            self.payments = None
            self.outbox = None
            self.processed_messages = None

    async def commit(self) -> None:
        """Commit the current transaction."""
        if self.session is None:
            msg = "UnitOfWork is not started"
            raise RuntimeError(msg)
        await self.session.commit()

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        if self.session is None:
            return
        await self.session.rollback()
