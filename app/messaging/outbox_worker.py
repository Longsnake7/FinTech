"""Outbox polling worker that publishes pending events to RabbitMQ."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.messaging.publisher import MessagePublisher
from app.messaging.retry import compute_retry_delay

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Polls the outbox table and publishes events to RabbitMQ."""

    def __init__(
        self,
        *,
        settings: Settings,
        uow_factory: Any,
        publisher: MessagePublisher,
        sleep: Any | None = None,
    ) -> None:
        self._settings = settings
        self._uow_factory = uow_factory
        self._publisher = publisher
        self._sleep = sleep or asyncio.sleep
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        """Signal the worker loop to stop."""
        self._stopped.set()

    async def run_forever(self) -> None:
        """Run until stop() is called."""
        logger.info("Outbox worker started")
        while not self._stopped.is_set():
            try:
                published = await self.publish_batch()
                if published == 0:
                    await self._wait(self._settings.outbox_poll_interval_seconds)
            except Exception:
                logger.exception("Outbox worker iteration failed")
                await self._wait(self._settings.outbox_poll_interval_seconds)
        logger.info("Outbox worker stopped")

    async def publish_batch(self) -> int:
        """Claim and publish a batch of pending outbox messages. Returns count published."""
        async with self._uow_factory() as uow:
            assert uow.outbox is not None
            messages = await uow.outbox.list_pending(limit=self._settings.outbox_batch_size)
            if not messages:
                return 0

            claimed = []
            for message in messages:
                lock_token = uuid4().hex
                await uow.outbox.mark_processing(message, lock_token=lock_token)
                claimed.append(message)
            await uow.commit()

        published = 0
        for message in claimed:
            try:
                await self._publisher.publish_payments_new(
                    dict(message.payload),
                    message_id=str(message.id),
                )
                async with self._uow_factory() as uow:
                    assert uow.outbox is not None
                    db_message = await uow.outbox.get_by_id(message.id)
                    if db_message is not None:
                        await uow.outbox.mark_published(db_message)
                        await uow.commit()
                published += 1
            except Exception as exc:
                logger.exception("Failed to publish outbox message %s", message.id)
                await self._handle_publish_failure(message.id, str(exc), message.attempts)
        return published

    async def _handle_publish_failure(
        self,
        message_id: Any,
        error: str,
        attempts: int,
    ) -> None:
        delay = compute_retry_delay(max(attempts, 1), self._settings)
        available_at = datetime.now(UTC) + timedelta(seconds=delay)
        failed = attempts >= self._settings.outbox_max_attempts
        async with self._uow_factory() as uow:
            assert uow.outbox is not None
            db_message = await uow.outbox.get_by_id(message_id)
            if db_message is None:
                return
            await uow.outbox.mark_retry(
                db_message,
                error=error,
                available_at=available_at,
                failed=failed,
            )
            await uow.commit()

    async def _wait(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stopped.wait(), timeout=seconds)
        except TimeoutError:
            return
